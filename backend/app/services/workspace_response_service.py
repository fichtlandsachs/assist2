# app/services/workspace_response_service.py
"""
HeyKarl Workspace Response Service.

Transforms HybridRetrievalResult into a structured, auditable JSON response
for the HeyKarl workspace. Enforces Guardrails:

  - Only evidence from official indexed sources
  - Explicit "no evidence" statement when nothing found
  - Architecture answers only with pattern evidence
  - Security answers only with permission/auth evidence
  - No hallucination: all fields derived from retrieved chunks only
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.services.hybrid_retrieval_service import HybridChunk, HybridRetrievalResult

# ── Output schema (matches the spec) ─────────────────────────────────────────

@dataclass
class EvidenceRef:
    source_system: str
    source_url:    str | None
    source_title:  str | None
    chunk_type:    str
    relevance:     float
    excerpt:       str

    def to_dict(self) -> dict:
        return {
            "source_system": self.source_system,
            "source_url":    self.source_url,
            "source_title":  self.source_title,
            "chunk_type":    self.chunk_type,
            "relevance":     round(self.relevance, 3),
            "excerpt":       self.excerpt[:400],
        }


@dataclass
class WorkspaceResponse:
    """
    Canonical HeyKarl workspace response.

    capability    — identified business capability (L1)
    process       — related process (L1–L3)
    objects       — business objects referenced across all systems
    roles         — roles and org units
    rules         — constraints, validation rules, authorization rules
    integration   — APIs, integration patterns, events
    source_systems— which systems contributed evidence
    evidence      — list of evidence references (source + excerpt)
    guardrail     — 'ok' | 'no_evidence' | 'insufficient_security' | 'insufficient_pattern'
    confidence    — 0.0–1.0
    """
    capability:     str
    process:        str
    objects:        list[str]
    roles:          list[str]
    rules:          list[str]
    integration:    list[str]
    source_systems: list[str]
    evidence:       list[EvidenceRef]
    guardrail:      Literal["ok", "no_evidence", "insufficient_security", "insufficient_pattern"]
    confidence:     float

    def to_dict(self) -> dict:
        return {
            "capability":     self.capability,
            "process":        self.process,
            "objects":        self.objects,
            "roles":          self.roles,
            "rules":          self.rules,
            "integration":    self.integration,
            "source_systems": self.source_systems,
            "evidence":       [e.to_dict() for e in self.evidence],
            "guardrail":      self.guardrail,
            "confidence":     round(self.confidence, 3),
        }

    def to_prompt_context(self) -> str:
        """Format for injection into LLM system prompt as grounded context."""
        lines = [
            "=== WORKSPACE CONTEXT (official documentation evidence) ===",
            f"Capability:  {self.capability or 'unbekannt'}",
            f"Process:     {self.process or 'unbekannt'}",
        ]
        if self.objects:
            lines.append(f"Objects:     {', '.join(self.objects)}")
        if self.roles:
            lines.append(f"Roles:       {', '.join(self.roles)}")
        if self.rules:
            lines.append(f"Rules:       {'; '.join(self.rules[:3])}")
        if self.integration:
            lines.append(f"Integration: {', '.join(self.integration)}")
        lines.append("")
        lines.append("Evidence:")
        for i, ev in enumerate(self.evidence[:5], 1):
            lines.append(f"  [{i}] {ev.source_system.upper()} | {ev.source_title or ev.source_url or '?'}")
            lines.append(f"      {ev.excerpt[:200]}")
        if self.guardrail != "ok":
            lines.append(f"\n⚠ Guardrail: {self.guardrail}")
        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)


# ── Guardrail checks ──────────────────────────────────────────────────────────

_SECURITY_KEYWORDS = re.compile(
    r"\b(security|permission|auth|oauth|mfa|encrypt|access control|role|sod|segregation)\b", re.I)
_ARCH_KEYWORDS = re.compile(
    r"\b(integration|architecture|pattern|api|idoc|odata|bapi|webhook|event-driven)\b", re.I)


def _needs_security_evidence(query: str) -> bool:
    return bool(_SECURITY_KEYWORDS.search(query))


def _needs_pattern_evidence(query: str) -> bool:
    return bool(_ARCH_KEYWORDS.search(query))


def _has_security_evidence(chunks: list[HybridChunk]) -> bool:
    return any(
        c.chunk_type in ("permission", "rule", "security") or
        bool(c.entities.get("permissions")) or
        bool(c.entities.get("roles"))
        for c in chunks
    )


def _has_pattern_evidence(chunks: list[HybridChunk]) -> bool:
    return any(
        c.chunk_type in ("integration_pattern", "api_reference") or
        bool(c.entities.get("patterns")) or
        bool(c.entities.get("apis"))
        for c in chunks
    )


# ── Entity merging ────────────────────────────────────────────────────────────

def _merge_entities(chunks: list[HybridChunk], key: str) -> list[str]:
    seen: list[str] = []
    for c in chunks:
        for v in c.entities.get(key, []):
            if v and v not in seen:
                seen.append(v)
    return seen[:15]


# ── Capability / process inference ────────────────────────────────────────────

def _infer_capability(chunks: list[HybridChunk]) -> str:
    for chunk in chunks:
        caps = chunk.entities.get("capability_candidates", [])  # type: ignore[call-overload]
        if isinstance(caps, list) and caps:
            return caps[0]
    # Fallback: source_title of top chunk
    if chunks and chunks[0].source_title:
        return chunks[0].source_title.split("|")[0].strip()
    return ""


def _infer_process(chunks: list[HybridChunk]) -> str:
    for chunk in chunks:
        procs = chunk.entities.get("process_candidates", [])  # type: ignore[call-overload]
        if isinstance(procs, list) and procs:
            return procs[0]
        flows = chunk.entities.get("processes") or chunk.entities.get("flows", [])
        if flows:
            return flows[0]
    return ""


# ── Main service ──────────────────────────────────────────────────────────────

class WorkspaceResponseService:
    """
    Transforms a HybridRetrievalResult into a structured WorkspaceResponse.
    Pure function — no DB, no LLM, no side effects.
    """

    def build(self, query: str, result: HybridRetrievalResult) -> WorkspaceResponse:
        """
        Args:
            query:  The original user query (used for guardrail classification).
            result: HybridRetrievalResult from hybrid_retrieve().

        Returns:
            WorkspaceResponse ready for serialisation and/or LLM injection.
        """
        if not result.has_results:
            return self._no_evidence_response()

        chunks = result.chunks

        # Determine guardrail
        guardrail: Literal["ok", "no_evidence", "insufficient_security", "insufficient_pattern"] = "ok"
        if _needs_security_evidence(query) and not _has_security_evidence(chunks):
            guardrail = "insufficient_security"
        elif _needs_pattern_evidence(query) and not _has_pattern_evidence(chunks):
            guardrail = "insufficient_pattern"

        # Build entity collections from all chunks
        objects     = _merge_entities(chunks, "objects")
        roles       = _merge_entities(chunks, "roles") + _merge_entities(chunks, "permissions")
        rules_raw   = _merge_entities(chunks, "rules")
        apis        = _merge_entities(chunks, "apis")
        patterns    = _merge_entities(chunks, "patterns")
        events      = _merge_entities(chunks, "events")
        integration = _unique(apis + patterns + events)

        # Deduplicate roles
        roles = list(dict.fromkeys(roles))[:10]

        # Extract normative rules from facts
        for chunk in chunks:
            for fact in chunk.entities.get("facts", []):
                if isinstance(fact, dict) and fact.get("kind") in ("constraint", "security_rule", "recommendation"):
                    rule_text = fact.get("object", "")[:200]
                    if rule_text and rule_text not in rules_raw:
                        rules_raw.append(rule_text)
        rules = rules_raw[:10]

        # Evidence references
        evidence = [
            EvidenceRef(
                source_system=c.source_system,
                source_url=c.source_url,
                source_title=c.source_title,
                chunk_type=c.chunk_type,
                relevance=c.final_score,
                excerpt=c.text[:400],
            )
            for c in chunks[:8]
        ]

        # Confidence = average final_score of top 3 chunks
        top3 = chunks[:3]
        confidence = sum(c.final_score for c in top3) / len(top3) if top3 else 0.0
        confidence = min(confidence * 2.5, 1.0)  # scale RRF scores (typically 0.1–0.5) to 0–1

        return WorkspaceResponse(
            capability=_infer_capability(chunks),
            process=_infer_process(chunks),
            objects=objects,
            roles=roles,
            rules=rules,
            integration=integration,
            source_systems=result.top_source_systems(),
            evidence=evidence,
            guardrail=guardrail,
            confidence=confidence,
        )

    def _no_evidence_response(self) -> WorkspaceResponse:
        return WorkspaceResponse(
            capability="",
            process="",
            objects=[],
            roles=[],
            rules=[],
            integration=[],
            source_systems=[],
            evidence=[],
            guardrail="no_evidence",
            confidence=0.0,
        )

    def format_no_evidence_message(self, query: str) -> str:
        return (
            "Für die Anfrage konnte keine Evidenz in der offiziellen Dokumentation gefunden werden.\n\n"
            f"Suchanfrage: **{query}**\n\n"
            "Bitte prüfe:\n"
            "- Ob die relevante Dokumentationsquelle (Salesforce, SAP, Jira, Confluence) bereits indexiert ist.\n"
            "- Ob die Anfrage spezifischer formuliert werden kann (Objektname, Prozessname, API-Name).\n\n"
            "_Hinweis: HeyKarl antwortet ausschließlich auf Basis offizieller, indexierter Dokumentation._"
        )


def _unique(lst: list[str]) -> list[str]:
    return list(dict.fromkeys(lst))
