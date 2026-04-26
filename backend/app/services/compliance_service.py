# app/services/compliance_service.py
"""
Compliance Assessment Service.

Core operations:
  - get_or_create_assessment     → find or create ComplianceAssessment for an object
  - refresh_assessment           → re-evaluate triggers, sync items, recompute scores
  - score_item                   → set score + status on a single item, write history
  - compute_assessment_summary   → recalculate overall scores, gate readiness, traffic light
  - create_snapshot              → persist frozen ComplianceStatusSnapshot
  - derive_traffic_light         → map numeric score to green/yellow/red/grey
  - derive_item_status           → map score to open/in_progress/fulfilled/deviation/etc.
  - compute_gate_impact          → string describing effect of a score change on gates
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_assessment import (
    ComplianceAssessment, ComplianceAssessmentItem, ComplianceScoreEntry,
    ComplianceStatusSnapshot,
    ItemStatus, ActivationSource, TrafficLight, OverallComplianceStatus,
    EvidenceStatus,
)
from app.models.product_governance import (
    ControlDefinition, ControlKind, ControlStatus, ControlCategory,
    DynamicTriggerRule, GateDefinition,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Traffic-light & status derivation ────────────────────────────────────────

def derive_traffic_light(score: int, hard_stop: bool = False) -> str:
    if score == 0:
        return TrafficLight.grey.value
    if score >= 3:
        return TrafficLight.green.value
    if score == 2:
        return TrafficLight.yellow.value
    # score == 1
    if hard_stop:
        return TrafficLight.red.value
    return TrafficLight.red.value


def derive_item_status(score: int, hard_stop: bool = False) -> str:
    if score == 0:
        return ItemStatus.open.value
    if score >= 3:
        return ItemStatus.fulfilled.value
    if score == 2:
        return ItemStatus.in_progress.value
    # score == 1
    if hard_stop:
        return ItemStatus.not_fulfilled.value
    return ItemStatus.deviation.value


def derive_blocks_gate(item: ComplianceAssessmentItem) -> bool:
    """Returns True if this item prevents a gate from being approved."""
    if not item.hard_stop:
        return False
    return item.score <= item.hard_stop_threshold


def compute_gate_impact(item: ComplianceAssessmentItem) -> Optional[str]:
    if derive_blocks_gate(item):
        gates = ", ".join(item.gate_phases)
        return (
            f"Hard-Stop-Control mit Score {item.score} ≤ {item.hard_stop_threshold}: "
            f"Gate {gates} kann nicht freigegeben werden."
        )
    if item.hard_stop and item.score == 2:
        gates = ", ".join(item.gate_phases)
        return f"Hard-Stop-Control mit Score 2: Gate {gates} nur Conditional Go möglich."
    return None


# ── Trigger evaluation (reuse from product_governance) ───────────────────────

def _evaluate_condition_tree(tree: dict, params: dict) -> bool:
    if not tree:
        return False
    if "operator" in tree:
        op = tree["operator"]
        conditions = tree.get("conditions", [])
        results = [_evaluate_condition_tree(c, params) for c in conditions]
        if op == "AND":
            return all(results)
        if op == "OR":
            return any(results)
        if op == "NOT":
            return not results[0] if results else True
    field = tree.get("field", "")
    op = tree.get("op", "eq")
    value = tree.get("value")
    actual = params.get(field)
    if actual is None:
        return False
    if op == "eq":
        return str(actual).lower() == str(value).lower()
    if op == "in":
        return str(actual).lower() in [str(v).lower() for v in (value or [])]
    if op == "gte":
        return _risk_level(actual) >= _risk_level(value)
    if op == "gt":
        return _risk_level(actual) > _risk_level(value)
    if op == "is_true":
        return bool(actual)
    return False


def _risk_level(v) -> int:
    levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return levels.get(str(v).lower(), 0)


# ── Core service functions ────────────────────────────────────────────────────

async def get_or_create_assessment(
    db: AsyncSession,
    org_id: uuid.UUID,
    object_type: str,
    object_id: uuid.UUID,
    object_name: str,
    context_params: dict,
    created_by: Optional[uuid.UUID] = None,
) -> ComplianceAssessment:
    """Get existing assessment or create a new one with initial items."""
    assessment = await db.scalar(
        select(ComplianceAssessment).where(
            and_(
                ComplianceAssessment.org_id == org_id,
                ComplianceAssessment.object_type == object_type,
                ComplianceAssessment.object_id == object_id,
            )
        )
    )
    if not assessment:
        assessment = ComplianceAssessment(
            org_id=org_id,
            object_type=object_type,
            object_id=object_id,
            object_name=object_name,
            context_params=context_params,
            created_by=created_by,
        )
        db.add(assessment)
        await db.flush()
        await _populate_items(db, assessment, context_params)
        await compute_assessment_summary(db, assessment)
        await db.flush()
    return assessment


async def refresh_assessment(
    db: AsyncSession,
    assessment: ComplianceAssessment,
    context_params: Optional[dict] = None,
) -> ComplianceAssessment:
    """
    Re-evaluate triggers with new context, add newly triggered controls,
    deactivate no-longer-applicable dynamic controls, and recompute summary.
    Does NOT reset scores of existing items.
    """
    params = context_params or assessment.context_params
    if context_params:
        assessment.context_params = context_params

    # Load existing item control IDs to avoid duplicates
    existing_result = await db.execute(
        select(ComplianceAssessmentItem.control_id, ComplianceAssessmentItem.activation_source)
        .where(ComplianceAssessmentItem.assessment_id == assessment.id)
    )
    existing_map = {str(row[0]): row[1] for row in existing_result.fetchall()}

    await _populate_items(db, assessment, params, existing_control_ids=set(existing_map.keys()))
    await compute_assessment_summary(db, assessment)
    assessment.last_refreshed_at = datetime.now(timezone.utc)
    await db.flush()
    return assessment


async def _populate_items(
    db: AsyncSession,
    assessment: ComplianceAssessment,
    params: dict,
    existing_control_ids: Optional[set] = None,
) -> None:
    """
    Load fixed controls + evaluate triggers → create ComplianceAssessmentItems
    for any controls not already present.
    """
    existing_control_ids = existing_control_ids or set()

    # Category name lookup
    cat_result = await db.execute(select(ControlCategory))
    cat_map: dict[str, str] = {str(c.id): c.name for c in cat_result.scalars().all()}

    # 1. Fixed controls (always active)
    fixed_result = await db.execute(
        select(ControlDefinition).where(
            and_(
                ControlDefinition.kind == ControlKind.fixed.value,
                ControlDefinition.status == ControlStatus.approved.value,
            )
        )
    )
    for ctrl in fixed_result.scalars().all():
        if str(ctrl.id) not in existing_control_ids:
            item = _make_item(assessment.id, ctrl, cat_map, ActivationSource.fixed.value)
            db.add(item)
            existing_control_ids.add(str(ctrl.id))

    # 2. Evaluate triggers → dynamic controls
    trigger_result = await db.execute(
        select(DynamicTriggerRule).where(DynamicTriggerRule.is_active == True)
    )
    for trigger in trigger_result.scalars().all():
        if not _evaluate_condition_tree(trigger.condition_tree, params):
            continue
        for ctrl_id_str in trigger.activates_control_ids:
            if ctrl_id_str in existing_control_ids:
                continue
            try:
                ctrl_id = uuid.UUID(str(ctrl_id_str))
            except (ValueError, AttributeError):
                continue
            ctrl = await db.get(ControlDefinition, ctrl_id)
            if ctrl and ctrl.status == ControlStatus.approved.value:
                item = _make_item(
                    assessment.id, ctrl, cat_map,
                    ActivationSource.trigger.value,
                    trigger_id=trigger.id,
                    trigger_name=trigger.name,
                )
                db.add(item)
                existing_control_ids.add(str(ctrl.id))

    await db.flush()


def _make_item(
    assessment_id: uuid.UUID,
    ctrl: ControlDefinition,
    cat_map: dict[str, str],
    activation_source: str,
    trigger_id: Optional[uuid.UUID] = None,
    trigger_name: Optional[str] = None,
    gate: Optional[str] = None,
) -> ComplianceAssessmentItem:
    return ComplianceAssessmentItem(
        assessment_id=assessment_id,
        control_id=ctrl.id,
        control_slug=ctrl.slug,
        control_name=ctrl.name,
        control_kind=ctrl.kind,
        category_name=cat_map.get(str(ctrl.category_id)) if ctrl.category_id else None,
        gate_phases=ctrl.gate_phases or [],
        hard_stop=ctrl.hard_stop,
        hard_stop_threshold=ctrl.hard_stop_threshold,
        default_weight=ctrl.default_weight,
        control_objective=ctrl.control_objective,
        why_relevant=ctrl.why_relevant,
        what_to_check=ctrl.what_to_check,
        guiding_questions=ctrl.guiding_questions or [],
        required_evidence_types=ctrl.evidence_requirements or [],
        responsible_role=ctrl.responsible_role,
        control_version=ctrl.version,
        activation_source=activation_source,
        activating_trigger_id=trigger_id,
        activating_trigger_name=trigger_name,
        activating_gate=gate,
        score=0,
        status=ItemStatus.open.value,
        traffic_light=TrafficLight.grey.value,
        evidence_status=EvidenceStatus.missing.value,
        blocks_gate=False,
    )


async def score_item(
    db: AsyncSession,
    item: ComplianceAssessmentItem,
    new_score: int,
    rationale: Optional[str],
    residual_risk: Optional[str],
    actor: User,
) -> ComplianceAssessmentItem:
    """Update score on an item, write score history, recompute gate blocks."""
    old_score = item.score
    old_status = item.status

    item.score = max(0, min(3, new_score))
    item.status = derive_item_status(item.score, item.hard_stop)
    item.traffic_light = derive_traffic_light(item.score, item.hard_stop)
    item.blocks_gate = derive_blocks_gate(item)
    if rationale is not None:
        item.rationale = rationale
    if residual_risk is not None:
        item.residual_risk = residual_risk
    item.assessed_by = actor.id
    item.assessed_by_name = getattr(actor, "full_name", None) or actor.email
    item.assessed_at = datetime.now(timezone.utc)

    gate_impact = compute_gate_impact(item)

    entry = ComplianceScoreEntry(
        item_id=item.id,
        from_score=old_score,
        to_score=item.score,
        from_status=old_status,
        to_status=item.status,
        rationale=rationale,
        gate_impact=gate_impact,
        changed_by=actor.id,
        changed_by_name=item.assessed_by_name,
    )
    db.add(entry)
    await db.flush()
    return item


async def compute_assessment_summary(
    db: AsyncSession,
    assessment: ComplianceAssessment,
) -> ComplianceAssessment:
    """Recompute aggregate fields on the assessment from its items."""
    items_result = await db.execute(
        select(ComplianceAssessmentItem).where(
            ComplianceAssessmentItem.assessment_id == assessment.id
        )
    )
    items = list(items_result.scalars().all())

    total = len(items)
    fulfilled = sum(1 for i in items if i.status == ItemStatus.fulfilled.value)
    deviation = sum(1 for i in items if i.status in (ItemStatus.deviation.value, ItemStatus.not_fulfilled.value))
    not_assessed = sum(1 for i in items if i.score == 0)
    hard_stop_total = sum(1 for i in items if i.hard_stop)
    hard_stop_critical = sum(1 for i in items if i.hard_stop and i.score <= i.hard_stop_threshold)

    # Weighted average score
    if total > 0:
        total_weight = sum(i.default_weight for i in items)
        if total_weight > 0:
            weighted_sum = sum(i.score * i.default_weight for i in items)
            overall_score = round(weighted_sum / total_weight, 2)
        else:
            overall_score = round(sum(i.score for i in items) / total, 2)
    else:
        overall_score = None

    # Traffic light
    if overall_score is None or not_assessed == total:
        tl = TrafficLight.grey.value
    elif hard_stop_critical > 0:
        tl = TrafficLight.red.value
    elif overall_score >= 2.5:
        tl = TrafficLight.green.value
    elif overall_score >= 1.5:
        tl = TrafficLight.yellow.value
    else:
        tl = TrafficLight.red.value

    # Compliance status
    if not_assessed == total or total == 0:
        status = OverallComplianceStatus.not_assessed.value
    elif hard_stop_critical > 0 or (overall_score is not None and overall_score < 1.5):
        status = OverallComplianceStatus.non_compliant.value
    elif deviation > 0 or (overall_score is not None and overall_score < 2.5):
        status = OverallComplianceStatus.partially_compliant.value
    else:
        status = OverallComplianceStatus.compliant.value

    # Gate readiness: per-gate, are all hard-stop controls satisfied?
    gate_readiness: dict[str, dict] = {}
    all_gates = {"G1", "G2", "G3", "G4"}
    for gate in all_gates:
        gate_items = [i for i in items if gate in i.gate_phases]
        hs_blocking = [i for i in gate_items if i.hard_stop and i.blocks_gate]
        unfulfilled = [i for i in gate_items if i.score == 0]
        if not gate_items:
            gate_readiness[gate] = {"status": "not_applicable", "blocking_count": 0}
        elif hs_blocking:
            gate_readiness[gate] = {
                "status": "blocked",
                "blocking_count": len(hs_blocking),
                "blocking_controls": [i.control_name for i in hs_blocking[:3]],
            }
        elif unfulfilled:
            gate_readiness[gate] = {
                "status": "incomplete",
                "unassessed_count": len(unfulfilled),
            }
        else:
            gate_items_scored = [i for i in gate_items if i.score > 0]
            avg = round(sum(i.score for i in gate_items_scored) / len(gate_items_scored), 2) if gate_items_scored else 0
            gate_readiness[gate] = {
                "status": "ready" if avg >= 2.0 else "conditional",
                "avg_score": avg,
            }

    assessment.total_controls = total
    assessment.fulfilled_controls = fulfilled
    assessment.deviation_controls = deviation
    assessment.not_assessed_controls = not_assessed
    assessment.hard_stop_total = hard_stop_total
    assessment.hard_stop_critical = hard_stop_critical
    assessment.overall_score = overall_score
    assessment.traffic_light = tl
    assessment.compliance_status = status
    assessment.gate_readiness = gate_readiness
    assessment.updated_at = datetime.now(timezone.utc)

    return assessment


async def create_snapshot(
    db: AsyncSession,
    assessment: ComplianceAssessment,
    trigger_reason: str,
    actor: Optional[User] = None,
) -> ComplianceStatusSnapshot:
    snapshot = ComplianceStatusSnapshot(
        assessment_id=assessment.id,
        trigger_reason=trigger_reason,
        compliance_status=assessment.compliance_status,
        overall_score=assessment.overall_score,
        traffic_light=assessment.traffic_light,
        gate_readiness=assessment.gate_readiness,
        summary={
            "total_controls": assessment.total_controls,
            "fulfilled_controls": assessment.fulfilled_controls,
            "deviation_controls": assessment.deviation_controls,
            "not_assessed_controls": assessment.not_assessed_controls,
            "hard_stop_total": assessment.hard_stop_total,
            "hard_stop_critical": assessment.hard_stop_critical,
        },
        created_by=actor.id if actor else None,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot
