# app/services/crawl/universal_entity_service.py
"""
Universal multi-system entity extractor for HeyKarl RAG.

Dispatches to system-specific sub-extractors based on `source_system`,
then maps results onto the canonical model.

Supported systems: salesforce | jira | confluence | sap
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.services.crawl.canonical_model import (
    CanonicalChunkMeta,
    CanonicalType,
    ChunkType,
    SourceSystem,
    infer_process_level,
    resolve_canonical_type,
)

# ── Common helpers ────────────────────────────────────────────────────────────

def _unique(lst: list[str]) -> list[str]:
    return list(dict.fromkeys(lst))


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


# ══════════════════════════════════════════════════════════════════════════════
# SALESFORCE sub-extractor
# ══════════════════════════════════════════════════════════════════════════════

_SF_OBJECT_ALLOWLIST = {
    "Account", "Contact", "Lead", "Opportunity", "Case", "Task", "Event",
    "User", "Profile", "Role", "Group", "Queue", "Campaign", "Contract",
    "Order", "Product2", "Pricebook2", "PricebookEntry", "Asset",
    "Entitlement", "WorkOrder", "ServiceAppointment", "Territory",
    "ContentDocument", "ContentVersion", "Attachment", "EmailMessage",
    "FeedItem", "CollaborationGroup", "Dashboard", "Report",
    "ApexClass", "ApexTrigger", "FlowDefinition", "FlowVersion",
    "CustomObject", "ValidationRule", "RecordType",
    "AuraDefinitionBundle", "LightningComponentBundle",
}
_SF_OBJ_RE   = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:__(?:c|mdt|e|b|x))?)\b")
_SF_FIELD_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+)\.([A-Za-z][a-zA-Z0-9_]+(?:__[cr])?)\b")
_SF_FLOW_RE  = re.compile(
    r"\b(Flow|Process Builder|Approval Process|Quick Action|Record-Triggered Flow"
    r"|Schedule-Triggered Flow|Platform Event|Autolaunched Flow)\b", re.I)
_SF_ROLE_RE  = re.compile(
    r"\b(Profile|Permission Set(?:\s+Group)?|Role Hierarchy|Field-Level Security|FLS"
    r"|Org-Wide Default|OWD|Record Type|System Administrator|Standard User)\b", re.I)
_SF_API_RE   = re.compile(
    r"\b(REST API|SOAP API|Bulk API(?:\s+2\.0)?|Streaming API|Tooling API"
    r"|Metadata API|Connect API|Composite API|SObject API|Apex REST)\b", re.I)
_SF_PAT_RE   = re.compile(
    r"\b(Request-Reply|Fire and Forget|Batch Data Synchronization|Remote Call-In"
    r"|UI Update Based on Data Changes|Data Virtualization|Publish-Subscribe"
    r"|Event-Driven|Change Data Capture|CDC|Named Credential|Platform Events?)\b", re.I)
_SF_NORM_RE  = [
    (re.compile(r"\b(recommended?|best practice|should|prefer)\b", re.I), "recommendation"),
    (re.compile(r"\b(avoid|do not|must not|never|not supported|deprecated|limit)\b", re.I), "constraint"),
    (re.compile(r"\b(require[sd]?|must|mandatory|enforce[sd]?|encrypt|authenticate|token|OAuth|MFA|IP restrict)\b", re.I), "security_rule"),
]


def _extract_salesforce(text: str, title: str, breadcrumb: list[str], source_key: str) -> dict:
    raw_obj = {m.group(1) for m in _SF_OBJ_RE.finditer(text)}
    objects = sorted(o for o in raw_obj if o in _SF_OBJECT_ALLOWLIST or re.search(r"__(?:c|mdt|e|b|x)$", o))
    fields  = sorted({f"{m.group(1)}.{m.group(2)}" for m in _SF_FIELD_RE.finditer(text)
                      if m.group(1) in _SF_OBJECT_ALLOWLIST or re.search(r"__(?:c|mdt|e|b|x)$", m.group(1))})
    flows   = _unique([m.group(0) for m in _SF_FLOW_RE.finditer(text)])
    roles   = sorted({m.group(0) for m in _SF_ROLE_RE.finditer(text)
                      if any(k in m.group(0) for k in ("Role", "Profile", "OWD", "Field-Level", "Record Type", "FLS", "Org-Wide"))})
    perms   = sorted({m.group(0) for m in _SF_ROLE_RE.finditer(text)
                      if any(k in m.group(0) for k in ("Permission", "System Admin", "Standard User"))})
    apis    = _unique([m.group(0) for m in _SF_API_RE.finditer(text)])
    patterns= _unique([m.group(0) for m in _SF_PAT_RE.finditer(text)])

    facts = []
    seen: set[str] = set()
    for sent in _sentences(text):
        if len(sent.strip()) < 20:
            continue
        for pat, kind in _SF_NORM_RE:
            if pat.search(sent):
                key = f"{kind}|{sent[:60]}"
                if key not in seen:
                    seen.add(key)
                    facts.append({"kind": kind, "subject": (objects[0] if objects else "Salesforce"), "predicate": kind, "object": sent.strip()[:300]})
                break

    return {
        "objects": objects, "fields": fields, "flows": flows,
        "roles": roles, "permissions": perms,
        "apis": apis, "patterns": patterns,
        "processes": flows, "steps": [],
        "events": [f for f in flows if "Event" in f],
        "rules": [f["object"] for f in facts if f["kind"] in ("constraint", "security_rule")],
        "facts": facts[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
# JIRA sub-extractor
# ══════════════════════════════════════════════════════════════════════════════

_JIRA_STATUS_RE = re.compile(
    r"\b(To Do|In Progress|In Review|Done|Blocked|Backlog|Closed|Resolved"
    r"|Open|Pending|Cancelled|Rejected|Approved|Waiting for Customer)\b", re.I)
_JIRA_ISSUE_TYPE_RE = re.compile(
    r"\b(Epic|Story|Task|Sub-task|Bug|Improvement|New Feature|Technical Debt"
    r"|Initiative|Feature|Spike|Risk)\b", re.I)
_JIRA_PERM_RE = re.compile(
    r"\b(Project Role|Permission Scheme|Global Permission|Issue Security Scheme"
    r"|Notification Scheme|Workflow Scheme|Project Administrator|Jira Administrator"
    r"|Service Desk Agent|Developer|Reporter)\b", re.I)
_JIRA_WORKFLOW_RE = re.compile(
    r"\b(Workflow|Transition|Post Function|Validator|Condition|Screen|Field Configuration"
    r"|Automation Rule|Trigger|Event|Board|Sprint|Backlog|Filter)\b", re.I)
_JIRA_API_RE = re.compile(
    r"\b(REST API|Jira API|Agile API|Jira Software API|Cloud API|Server API"
    r"|Webhook|Connect App|Forge App|OAuth 2\.0|Basic Auth|PAT)\b", re.I)
_JIRA_NORM_RE = [
    (re.compile(r"\b(recommended?|best practice|should|consider)\b", re.I), "recommendation"),
    (re.compile(r"\b(avoid|do not|deprecated|limit|maximum|not supported)\b", re.I), "constraint"),
    (re.compile(r"\b(require[sd]?|must|mandatory|permission|role|access)\b", re.I), "security_rule"),
]


def _extract_jira(text: str, title: str, breadcrumb: list[str], source_key: str) -> dict:
    statuses    = _unique([m.group(0) for m in _JIRA_STATUS_RE.finditer(text)])
    issue_types = _unique([m.group(0) for m in _JIRA_ISSUE_TYPE_RE.finditer(text)])
    perms       = _unique([m.group(0) for m in _JIRA_PERM_RE.finditer(text)])
    workflows   = _unique([m.group(0) for m in _JIRA_WORKFLOW_RE.finditer(text)])
    apis        = _unique([m.group(0) for m in _JIRA_API_RE.finditer(text)])

    facts = []
    seen: set[str] = set()
    for sent in _sentences(text):
        if len(sent.strip()) < 20:
            continue
        for pat, kind in _JIRA_NORM_RE:
            if pat.search(sent):
                key = f"{kind}|{sent[:60]}"
                if key not in seen:
                    seen.add(key)
                    facts.append({"kind": kind, "subject": (issue_types[0] if issue_types else "Jira"), "predicate": kind, "object": sent.strip()[:300]})
                break

    return {
        "objects":     issue_types,
        "fields":      [],
        "flows":       [w for w in workflows if "Workflow" in w or "Automation" in w],
        "roles":       [p for p in perms if any(k in p for k in ("Administrator", "Agent", "Developer", "Reporter"))],
        "permissions": [p for p in perms if any(k in p for k in ("Scheme", "Permission", "Role"))],
        "apis":        apis,
        "patterns":    [],
        "processes":   [w for w in workflows if "Workflow" in w],
        "steps":       statuses,
        "events":      [w for w in workflows if "Event" in w or "Trigger" in w or "Webhook" in w],
        "rules":       [f["object"] for f in facts if f["kind"] in ("constraint",)],
        "facts":       facts[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CONFLUENCE sub-extractor
# ══════════════════════════════════════════════════════════════════════════════

_CONF_SPACE_RE = re.compile(
    r"\b(Space|Knowledge Base|Team Space|Personal Space|Documentation|Wiki)\b", re.I)
_CONF_TEMPLATE_RE = re.compile(
    r"\b(Template|Blueprint|Meeting Notes?|Decision|Project Plan|Retrospective"
    r"|How-to|Runbook|ADR|Architecture Decision Record)\b", re.I)
_CONF_PERM_RE = re.compile(
    r"\b(Space Permission|Page Restriction|Group|User|Anonymous Access"
    r"|Administrator|Confluence Administrator|Space Admin)\b", re.I)
_CONF_API_RE = re.compile(
    r"\b(REST API|Confluence API|Cloud API|Server API|Content API"
    r"|Webhook|OAuth 2\.0|PAT|Personal Access Token|Forge App|Connect App)\b", re.I)
_CONF_NORM_RE = [
    (re.compile(r"\b(recommended?|best practice|should|prefer)\b", re.I), "recommendation"),
    (re.compile(r"\b(avoid|do not|deprecated|limit|not supported)\b", re.I), "constraint"),
    (re.compile(r"\b(require[sd]?|must|permission|restrict)\b", re.I), "security_rule"),
]


def _extract_confluence(text: str, title: str, breadcrumb: list[str], source_key: str) -> dict:
    spaces    = _unique([m.group(0) for m in _CONF_SPACE_RE.finditer(text)])
    templates = _unique([m.group(0) for m in _CONF_TEMPLATE_RE.finditer(text)])
    perms     = _unique([m.group(0) for m in _CONF_PERM_RE.finditer(text)])
    apis      = _unique([m.group(0) for m in _CONF_API_RE.finditer(text)])

    facts = []
    seen: set[str] = set()
    for sent in _sentences(text):
        if len(sent.strip()) < 20:
            continue
        for pat, kind in _CONF_NORM_RE:
            if pat.search(sent):
                key = f"{kind}|{sent[:60]}"
                if key not in seen:
                    seen.add(key)
                    facts.append({"kind": kind, "subject": "Confluence", "predicate": kind, "object": sent.strip()[:300]})
                break

    return {
        "objects":     templates,
        "fields":      [],
        "flows":       [],
        "roles":       [p for p in perms if any(k in p for k in ("Administrator", "Admin", "User", "Group"))],
        "permissions": [p for p in perms if any(k in p for k in ("Permission", "Restriction", "Access"))],
        "apis":        apis,
        "patterns":    [],
        "processes":   [],
        "steps":       [],
        "events":      [a for a in apis if "Webhook" in a],
        "rules":       [f["object"] for f in facts if f["kind"] == "constraint"],
        "facts":       facts[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
# SAP S/4HANA sub-extractor
# ══════════════════════════════════════════════════════════════════════════════

_SAP_OBJECT_RE = re.compile(
    r"\b(Sales Order|Purchase Order|Delivery|Invoice|Material|Vendor|Customer"
    r"|Cost Center|Profit Center|Plant|Company Code|Business Partner"
    r"|Work Order|Service Order|Quotation|Contract|Production Order"
    r"|Asset|GL Account|Cost Element|Activity Type)\b", re.I)
_SAP_PROCESS_RE = re.compile(
    r"\b(Order-to-Cash|Procure-to-Pay|Record-to-Report|Hire-to-Retire"
    r"|Plan-to-Produce|Idea-to-Market|Asset Lifecycle|Financial Close"
    r"|Lead-to-Order|Service-to-Cash)\b", re.I)
_SAP_STEP_RE = re.compile(
    r"\b(Create|Post|Release|Confirm|Approve|Reject|Close|Complete|Print"
    r"|Goods Receipt|Goods Issue|Invoice Verification|Payment Run"
    r"|Billing|Delivery|Picking|Packing|Transfer Order)\b", re.I)
_SAP_ROLE_RE = re.compile(
    r"\b(Business User|Key User|Administrator|SAP Basis|Accountant|Buyer"
    r"|Sales Rep|Warehouse Clerk|Plant Manager|Controller|HR Manager"
    r"|IT Administrator|Org Unit|Position|Job)\b", re.I)
_SAP_PERM_RE = re.compile(
    r"\b(Authorization Object|Role Concept|Profile|Authorization Check"
    r"|Object Class|SU24|PFCG|Authorization Group|Field-Level Access"
    r"|Structural Authorization)\b", re.I)
_SAP_API_RE = re.compile(
    r"\b(BAPI|OData Service|RFC|IDoc|SOAP Service|REST API|SAP API"
    r"|Business Hub|Communication Arrangement|Integration Suite"
    r"|SAP Integration|CPI|BTP|ABAP API)\b", re.I)
_SAP_EVENT_RE = re.compile(
    r"\b(BAdI|User Exit|Enhancement Point|Business Event|Change Pointer"
    r"|IDOC|ALE|EDI|Change Document|BAPI Event)\b", re.I)
_SAP_RULE_RE = re.compile(
    r"\b(Customizing|Configuration|IMG|Business Rule|Validation|Substitution"
    r"|Tolerance Group|Posting Period|Fiscal Year Variant|Chart of Accounts)\b", re.I)
_SAP_NORM_RE = [
    (re.compile(r"\b(recommended?|best practice|should|advise)\b", re.I), "recommendation"),
    (re.compile(r"\b(avoid|do not|must not|deprecated|not supported|limit)\b", re.I), "constraint"),
    (re.compile(r"\b(require[sd]?|must|mandatory|authorization|access control|segregation of duties|SoD)\b", re.I), "security_rule"),
]


def _extract_sap(text: str, title: str, breadcrumb: list[str], source_key: str) -> dict:
    objects   = _unique([m.group(0) for m in _SAP_OBJECT_RE.finditer(text)])
    processes = _unique([m.group(0) for m in _SAP_PROCESS_RE.finditer(text)])
    steps     = _unique([m.group(0) for m in _SAP_STEP_RE.finditer(text)])
    roles     = _unique([m.group(0) for m in _SAP_ROLE_RE.finditer(text)])
    perms     = _unique([m.group(0) for m in _SAP_PERM_RE.finditer(text)])
    apis      = _unique([m.group(0) for m in _SAP_API_RE.finditer(text)])
    events    = _unique([m.group(0) for m in _SAP_EVENT_RE.finditer(text)])
    rules     = _unique([m.group(0) for m in _SAP_RULE_RE.finditer(text)])

    facts = []
    seen: set[str] = set()
    for sent in _sentences(text):
        if len(sent.strip()) < 20:
            continue
        for pat, kind in _SAP_NORM_RE:
            if pat.search(sent):
                key = f"{kind}|{sent[:60]}"
                if key not in seen:
                    seen.add(key)
                    subj = processes[0] if processes else (objects[0] if objects else "SAP")
                    facts.append({"kind": kind, "subject": subj, "predicate": kind, "object": sent.strip()[:300]})
                break

    return {
        "objects":     objects,
        "fields":      [],
        "flows":       processes,
        "roles":       roles,
        "permissions": perms,
        "apis":        apis,
        "patterns":    [],
        "processes":   processes,
        "steps":       steps,
        "events":      events,
        "rules":       rules,
        "facts":       facts[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Chunk-type classifier (universal)
# ══════════════════════════════════════════════════════════════════════════════

def _classify_chunk(
    source_system: str,
    title: str,
    breadcrumb: list[str],
    text: str,
    entities: dict,
) -> ChunkType:
    ctx = " ".join([title] + breadcrumb + [text[:300]]).lower()

    if any(k in ctx for k in ("security", "authentication", "oauth", "mfa", "encryption", "authorization", "sod", "segregation")):
        return "permission" if entities.get("permissions") else "rule"
    if any(k in ctx for k in ("integration", "api", "idoc", "odata", "bapi", "rest api", "soap", "webhook")):
        if entities.get("patterns") or "pattern" in ctx:
            return "integration_pattern"
        return "api_reference"
    if any(k in ctx for k in ("workflow", "flow", "process", "order-to-cash", "procure-to-pay", "transition")):
        if any(k in ctx for k in ("step", "status", "activity", "transition")):
            return "process_step"
        return "process_overview"
    if any(k in ctx for k in ("field", "attribute", "column", "property")):
        return "object_field"
    if any(k in ctx for k in ("object", "entity", "table", "standard object", "business object")):
        return "object_overview"
    if any(k in ctx for k in ("best practice", "recommended", "guideline")):
        return "best_practice"
    if any(k in ctx for k in ("constraint", "limit", "avoid", "not supported", "deprecated")):
        return "constraint"
    if any(k in ctx for k in ("permission", "role", "profile", "authorization")):
        return "permission"
    if source_system == "confluence":
        return "knowledge_object"
    if entities.get("steps"):
        return "process_step"
    if entities.get("processes") or entities.get("flows"):
        return "workflow"
    return "general"


# ══════════════════════════════════════════════════════════════════════════════
# Universal extractor — public API
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UniversalExtractionResult:
    source_system:         str
    canonical_type:        CanonicalType
    chunk_type:            ChunkType
    entities:              dict
    facts:                 list[dict]
    capability_candidates: list[str]
    process_candidates:    list[str]
    process_level:         str
    audit_relevance:       str
    integration_relevance: str
    summary:               str

    def to_chunk_meta(self, vendor: str = "", doc_category: str = "", language: str = "en") -> dict:
        """Return flat dict suitable for storing as source_metadata in ChunkingService."""
        return {
            "source_system":         self.source_system,
            "canonical_type":        self.canonical_type,
            "chunk_type":            self.chunk_type,
            "entities":              self.entities,
            "capability_candidates": self.capability_candidates,
            "process_candidates":    self.process_candidates,
            "process_level":         self.process_level,
            "audit_relevance":       self.audit_relevance,
            "integration_relevance": self.integration_relevance,
            "vendor":                vendor,
            "doc_category":          doc_category,
            "language":              language,
        }

    def to_dict(self) -> dict:
        return {
            "summary":               self.summary,
            "source_system":         self.source_system,
            "canonical_type":        self.canonical_type,
            "chunk_type":            self.chunk_type,
            "entities":              self.entities,
            "facts":                 self.facts,
            "capability_candidates": self.capability_candidates,
            "process_candidates":    self.process_candidates,
            "process_level":         self.process_level,
            "audit_relevance":       self.audit_relevance,
            "integration_relevance": self.integration_relevance,
        }


_DISPATCH: dict[str, callable] = {
    "salesforce": _extract_salesforce,
    "jira":       _extract_jira,
    "confluence": _extract_confluence,
    "sap":        _extract_sap,
}


class UniversalEntityExtractor:
    """
    Single entry point for multi-system entity extraction.
    Determines source_system from metadata_defaults['vendor'] or source_key prefix,
    then delegates to the appropriate sub-extractor.
    """

    def extract(
        self,
        text: str,
        page_title: str = "",
        breadcrumb: list[str] | None = None,
        source_key: str = "",
        metadata_defaults: dict | None = None,
    ) -> UniversalExtractionResult:
        breadcrumb = breadcrumb or []
        metadata_defaults = metadata_defaults or {}

        source_system = self._detect_system(source_key, metadata_defaults)
        extractor_fn  = _DISPATCH.get(source_system, _extract_salesforce)

        raw = extractor_fn(text, page_title, breadcrumb, source_key)
        entities = {k: raw[k] for k in ("objects", "fields", "flows", "roles", "permissions", "apis", "patterns", "processes", "steps", "events", "rules")}
        facts    = raw.get("facts", [])

        chunk_type    = _classify_chunk(source_system, page_title, breadcrumb, text, entities)
        canonical_type = self._infer_canonical_type(source_system, chunk_type, entities)
        process_level  = infer_process_level(breadcrumb, chunk_type)
        caps, procs    = self._build_candidates(breadcrumb, page_title, entities, source_system)
        audit_rel      = self._audit_relevance(entities, facts)
        integ_rel      = self._integration_relevance(entities, facts, source_key)
        summary        = self._summary(page_title, breadcrumb, entities, source_system, chunk_type)

        return UniversalExtractionResult(
            source_system=source_system,
            canonical_type=canonical_type,
            chunk_type=chunk_type,
            entities=entities,
            facts=facts,
            capability_candidates=caps,
            process_candidates=procs,
            process_level=process_level,
            audit_relevance=audit_rel,
            integration_relevance=integ_rel,
            summary=summary,
        )

    # ── System detection ─────────────────────────────────────────────────────

    def _detect_system(self, source_key: str, metadata_defaults: dict) -> SourceSystem:
        vendor = metadata_defaults.get("vendor", "").lower()
        if vendor in ("salesforce",):
            return "salesforce"
        if vendor in ("atlassian", "jira"):
            return "jira"
        if vendor in ("confluence",):
            return "confluence"
        if vendor in ("sap",):
            return "sap"
        key = source_key.lower()
        if key.startswith("sf_") or "salesforce" in key:
            return "salesforce"
        if key.startswith("jira") or "jira" in key:
            return "jira"
        if key.startswith("confluence") or "confluence" in key:
            return "confluence"
        if key.startswith("sap") or "sap" in key:
            return "sap"
        return "salesforce"  # safe default

    # ── Canonical type inference ─────────────────────────────────────────────

    def _infer_canonical_type(
        self, source_system: str, chunk_type: ChunkType, entities: dict
    ) -> CanonicalType:
        mapping: dict[ChunkType, CanonicalType] = {
            "object_overview":    "BusinessObject",
            "object_field":       "BusinessObject",
            "process_overview":   "Process",
            "process_step":       "ProcessStep",
            "workflow":           "Process",
            "rule":               "Rule",
            "permission":         "Permission",
            "integration_pattern":"Integration",
            "api_reference":      "API",
            "best_practice":      "Rule",
            "constraint":         "Rule",
            "knowledge_object":   "KnowledgeObject",
            "general":            "Capability",
        }
        return mapping.get(chunk_type, "BusinessObject")

    # ── Capability & process candidates ─────────────────────────────────────

    def _build_candidates(
        self, breadcrumb: list[str], title: str, entities: dict, source_system: str
    ) -> tuple[list[str], list[str]]:
        caps: list[str] = []
        procs: list[str] = []
        if breadcrumb:
            caps.append(breadcrumb[0])
        if len(breadcrumb) > 1:
            procs.append(breadcrumb[1])
        caps.extend(entities.get("objects", [])[:2])
        procs.extend(entities.get("processes", entities.get("flows", []))[:2])
        procs.extend(entities.get("apis", [])[:2])
        return _unique(caps), _unique(procs)

    # ── Relevance scoring ────────────────────────────────────────────────────

    def _audit_relevance(self, entities: dict, facts: list[dict]) -> str:
        score  = len([f for f in facts if f["kind"] == "security_rule"]) * 3
        score += len(entities.get("permissions", [])) * 2
        score += len(entities.get("roles", []))
        if score >= 6: return "high"
        if score >= 2: return "medium"
        return "low"

    def _integration_relevance(self, entities: dict, facts: list[dict], source_key: str) -> str:
        score  = len(entities.get("apis", [])) * 2
        score += len(entities.get("patterns", [])) * 2
        score += len(entities.get("events", []))
        if "integration" in source_key.lower() or "api" in source_key.lower():
            score += 3
        if score >= 6: return "high"
        if score >= 2: return "medium"
        return "low"

    # ── Summary ──────────────────────────────────────────────────────────────

    def _summary(
        self, title: str, breadcrumb: list[str], entities: dict,
        source_system: str, chunk_type: str,
    ) -> str:
        parts = []
        if title:
            parts.append(title)
        if breadcrumb:
            parts.append(" › ".join(breadcrumb))
        highlights = []
        for key, label in [("objects", "Objects"), ("processes", "Processes"), ("apis", "APIs"), ("patterns", "Patterns")]:
            vals = entities.get(key, [])
            if vals:
                highlights.append(f"{label}: {', '.join(vals[:3])}")
        if highlights:
            parts.append(" | ".join(highlights))
        return " — ".join(parts) or f"{source_system.title()} {chunk_type} documentation"
