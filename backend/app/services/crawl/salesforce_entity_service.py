# app/services/crawl/salesforce_entity_service.py
"""
Salesforce-specific entity extraction for RAG chunks.

Extracts structured entities from Salesforce documentation text:
  objects, fields, flows, roles/profiles/permissions, APIs,
  integration patterns, and normative rules (recommendations,
  constraints, security rules).

Operates entirely on plain text — no LLM call, no hallucination risk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ── Compiled patterns ─────────────────────────────────────────────────────────

# Salesforce standard + common custom object names (CamelCase, optional __c/__mdt/__e)
_OBJ_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+(?:__c|__mdt|__e|__b|__x)?)\b"
)

# API field names: ObjectName.FieldName or standalone Api__c / Name / Id etc.
_FIELD_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+)\.([A-Za-z][a-zA-Z0-9_]+(?:__c|__r)?)\b"
)

# Flow / Process Builder / Approval Process references
_FLOW_RE = re.compile(
    r"\b(Flow|Process Builder|Approval Process|Quick Action|Record-Triggered Flow"
    r"|Schedule-Triggered Flow|Platform Event|Autolaunched Flow)\b",
    re.IGNORECASE,
)

# Profiles, Roles, Permission Sets
_ROLE_RE = re.compile(
    r"\b(System Administrator|Standard User|Chatter Free User"
    r"|Profile|Permission Set|Permission Set Group|Role Hierarchy"
    r"|Org-Wide Default|OWD|Field-Level Security|FLS|Record Type)\b",
    re.IGNORECASE,
)

# REST / SOAP / Bulk / Streaming / Tooling / Metadata / Connect API patterns
_API_RE = re.compile(
    r"\b(REST API|SOAP API|Bulk API(?:\s+2\.0)?|Streaming API"
    r"|Tooling API|Metadata API|Connect API|Composite API"
    r"|SObject API|Apex REST|Analytics API|Reports API)\b",
    re.IGNORECASE,
)

# Integration patterns
_PATTERN_RE = re.compile(
    r"\b(Request-Reply|Fire and Forget|Batch Data Synchronization"
    r"|Remote Call-In|UI Update Based on Data Changes"
    r"|Data Virtualization|Publish-Subscribe|Event-Driven"
    r"|Point-to-Point|Enterprise Service Bus|ESB"
    r"|Outbound Messaging|Change Data Capture|CDC"
    r"|Platform Events?|Named Credential)\b",
    re.IGNORECASE,
)

# Normative language — maps to fact kind
_NORMATIVE: list[tuple[re.Pattern, Literal["recommendation", "constraint", "security_rule"]]] = [
    (re.compile(r"\b(recommended?|best practice|should|prefer)\b", re.IGNORECASE), "recommendation"),
    (re.compile(r"\b(avoid|do not|must not|never|not supported|deprecated|limit)\b", re.IGNORECASE), "constraint"),
    (re.compile(r"\b(require[sd]?|must|mandatory|enforce[sd]?|encrypt|authenticate|token|OAuth|MFA|IP restrict)\b", re.IGNORECASE), "security_rule"),
]

# Salesforce object allowlist — avoids common English words being matched
_SF_OBJECTS = {
    "Account", "Contact", "Lead", "Opportunity", "Case", "Task", "Event",
    "User", "Profile", "Role", "Group", "Queue", "Campaign", "Contract",
    "Order", "Product2", "Pricebook2", "PricebookEntry", "Asset", "Entitlement",
    "WorkOrder", "ServiceAppointment", "OperatingHours", "Shift", "Territory",
    "ContentDocument", "ContentVersion", "Attachment", "Note", "EmailMessage",
    "FeedItem", "CollaborationGroup", "Dashboard", "Report", "ListView",
    "ApexClass", "ApexTrigger", "FlowDefinition", "FlowVersion",
    "CustomObject", "CustomField", "ValidationRule", "WorkflowRule",
    "ProcessDefinition", "ApprovalProcess", "RecordType", "FieldSet",
    "AuraDefinitionBundle", "LightningComponentBundle",
}


# ── Output schema ─────────────────────────────────────────────────────────────

@dataclass
class SalesforceEntities:
    objects:     list[str] = field(default_factory=list)
    fields:      list[str] = field(default_factory=list)
    flows:       list[str] = field(default_factory=list)
    roles:       list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    apis:        list[str] = field(default_factory=list)
    patterns:    list[str] = field(default_factory=list)


@dataclass
class SalesforceFact:
    kind:      Literal["definition", "recommendation", "constraint", "security_rule", "integration_rule"]
    subject:   str
    predicate: str
    object:    str


@dataclass
class SalesforceExtractionResult:
    summary:               str
    chunk_type:            str
    entities:              SalesforceEntities
    facts:                 list[SalesforceFact]
    capability_candidates: list[str]
    process_candidates:    list[str]
    audit_relevance:       Literal["low", "medium", "high"]
    integration_relevance: Literal["low", "medium", "high"]

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "chunk_type": self.chunk_type,
            "entities": {
                "objects":     self.entities.objects,
                "fields":      self.entities.fields,
                "flows":       self.entities.flows,
                "roles":       self.entities.roles,
                "permissions": self.entities.permissions,
                "apis":        self.entities.apis,
                "patterns":    self.entities.patterns,
            },
            "facts": [
                {
                    "kind":      f.kind,
                    "subject":   f.subject,
                    "predicate": f.predicate,
                    "object":    f.object,
                }
                for f in self.facts
            ],
            "capability_candidates": self.capability_candidates,
            "process_candidates":    self.process_candidates,
            "audit_relevance":       self.audit_relevance,
            "integration_relevance": self.integration_relevance,
        }


# ── Extractor ─────────────────────────────────────────────────────────────────

class SalesforceEntityExtractor:
    """
    Deterministic, regex-based entity extractor for Salesforce documentation.
    No LLM — zero hallucination risk. Fast enough to run inline during indexing.
    """

    def extract(
        self,
        text: str,
        page_title: str = "",
        breadcrumb: list[str] | None = None,
        source_key: str = "",
    ) -> SalesforceExtractionResult:
        breadcrumb = breadcrumb or []
        sentences = self._split_sentences(text)

        entities   = self._extract_entities(text)
        facts      = self._extract_facts(sentences, entities)
        chunk_type = self._classify_chunk(page_title, breadcrumb, text, entities)
        caps, procs = self._capability_candidates(breadcrumb, page_title, entities)

        audit_rel = self._audit_relevance(entities, facts)
        integ_rel = self._integration_relevance(entities, facts, source_key)

        summary = self._build_summary(page_title, breadcrumb, entities, chunk_type)

        return SalesforceExtractionResult(
            summary=summary,
            chunk_type=chunk_type,
            entities=entities,
            facts=facts,
            capability_candidates=caps,
            process_candidates=procs,
            audit_relevance=audit_rel,
            integration_relevance=integ_rel,
        )

    # ── Entity extraction ────────────────────────────────────────────────────

    def _extract_entities(self, text: str) -> SalesforceEntities:
        ent = SalesforceEntities()

        # Objects: only well-known SF objects or __c / __mdt / __e / __b suffixed
        raw_objects = {m.group(1) for m in _OBJ_RE.finditer(text)}
        ent.objects = sorted(
            o for o in raw_objects
            if o in _SF_OBJECTS or re.search(r"__(?:c|mdt|e|b|x)$", o)
        )

        # Fields: Object.Field pairs
        ent.fields = sorted({
            f"{m.group(1)}.{m.group(2)}"
            for m in _FIELD_RE.finditer(text)
            if m.group(1) in _SF_OBJECTS or re.search(r"__(?:c|mdt|e|b|x)$", m.group(1))
        })

        # Flows / automation
        ent.flows = sorted({m.group(0) for m in _FLOW_RE.finditer(text)})

        # Roles / profiles / permissions
        all_role_matches = [m.group(0) for m in _ROLE_RE.finditer(text)]
        role_terms   = {"Profile", "Role", "Role Hierarchy", "OWD", "Org-Wide Default",
                        "Record Type", "Field-Level Security", "FLS"}
        perm_terms   = {"Permission Set", "Permission Set Group", "System Administrator",
                        "Standard User", "Chatter Free User"}
        ent.roles       = sorted({m for m in all_role_matches if any(t in m for t in role_terms)})
        ent.permissions = sorted({m for m in all_role_matches if any(t in m for t in perm_terms)})

        # APIs
        ent.apis = sorted({m.group(0) for m in _API_RE.finditer(text)})

        # Integration patterns
        ent.patterns = sorted({m.group(0) for m in _PATTERN_RE.finditer(text)})

        return ent

    # ── Fact extraction ──────────────────────────────────────────────────────

    def _extract_facts(
        self, sentences: list[str], entities: SalesforceEntities
    ) -> list[SalesforceFact]:
        facts: list[SalesforceFact] = []
        seen: set[str] = set()

        for sent in sentences:
            sent_clean = sent.strip()
            if len(sent_clean) < 20:
                continue

            for pattern, kind in _NORMATIVE:
                if not pattern.search(sent_clean):
                    continue

                subject = self._extract_subject(sent_clean, entities)
                key = f"{kind}|{subject}|{sent_clean[:60]}"
                if key in seen:
                    continue
                seen.add(key)

                facts.append(SalesforceFact(
                    kind=kind,
                    subject=subject,
                    predicate=kind,
                    object=sent_clean[:300],
                ))
                break  # one fact per sentence

        return facts[:30]  # cap to avoid noise

    def _extract_subject(self, sentence: str, entities: SalesforceEntities) -> str:
        """Best-effort subject: first mentioned entity, fallback to first noun phrase."""
        for obj in entities.objects:
            if obj in sentence:
                return obj
        for api in entities.apis:
            if api.lower() in sentence.lower():
                return api
        for flow in entities.flows:
            if flow.lower() in sentence.lower():
                return flow
        # Fallback: first capitalised word sequence
        m = re.search(r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3})\b", sentence)
        return m.group(1) if m else "Salesforce"

    # ── Chunk classification ─────────────────────────────────────────────────

    def _classify_chunk(
        self,
        title: str,
        breadcrumb: list[str],
        text: str,
        entities: SalesforceEntities,
    ) -> str:
        context = " ".join([title] + breadcrumb + [text[:300]]).lower()
        if any(k in context for k in ("security", "well-architected", "authentication", "oauth", "mfa", "encryption")):
            return "security"
        if any(k in context for k in ("integration pattern", "middleware", "event-driven", "api limit", "callout")):
            return "integration"
        if entities.flows:
            return "automation"
        if any(k in context for k in ("metadata api", "tooling api", "deploy", "retrieve", "package")):
            return "metadata"
        if any(k in context for k in ("object reference", "fields", "field types", "standard object")):
            return "object_reference"
        return "general"

    # ── Capability / process candidates ─────────────────────────────────────

    def _capability_candidates(
        self, breadcrumb: list[str], title: str, entities: SalesforceEntities
    ) -> tuple[list[str], list[str]]:
        caps: list[str] = []
        procs: list[str] = []

        # Breadcrumb top-level → capability, second level → process
        if breadcrumb:
            caps.append(breadcrumb[0])
        if len(breadcrumb) > 1:
            procs.append(breadcrumb[1])

        # Objects map to capabilities
        caps.extend(entities.objects[:3])

        # APIs map to integration processes
        procs.extend(entities.apis[:3])

        return list(dict.fromkeys(caps)), list(dict.fromkeys(procs))

    # ── Relevance scoring ────────────────────────────────────────────────────

    def _audit_relevance(
        self, entities: SalesforceEntities, facts: list[SalesforceFact]
    ) -> Literal["low", "medium", "high"]:
        score = 0
        score += len([f for f in facts if f.kind == "security_rule"]) * 3
        score += len(entities.permissions) * 2
        score += len(entities.roles)
        if score >= 6:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    def _integration_relevance(
        self,
        entities: SalesforceEntities,
        facts: list[SalesforceFact],
        source_key: str,
    ) -> Literal["low", "medium", "high"]:
        score = 0
        score += len(entities.apis) * 2
        score += len(entities.patterns) * 2
        score += len([f for f in facts if f.kind == "integration_rule"])
        if "integration" in source_key.lower():
            score += 3
        if score >= 6:
            return "high"
        if score >= 2:
            return "medium"
        return "low"

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _split_sentences(self, text: str) -> list[str]:
        return re.split(r"(?<=[.!?])\s+", text)

    def _build_summary(
        self,
        title: str,
        breadcrumb: list[str],
        entities: SalesforceEntities,
        chunk_type: str,
    ) -> str:
        parts = []
        if title:
            parts.append(title)
        if breadcrumb:
            parts.append(" › ".join(breadcrumb))
        highlights: list[str] = []
        if entities.objects:
            highlights.append(f"Objects: {', '.join(entities.objects[:5])}")
        if entities.apis:
            highlights.append(f"APIs: {', '.join(entities.apis[:3])}")
        if entities.patterns:
            highlights.append(f"Patterns: {', '.join(entities.patterns[:3])}")
        if highlights:
            parts.append(" | ".join(highlights))
        return " — ".join(parts) or f"Salesforce {chunk_type} documentation"
