# app/services/crawl/canonical_model.py
"""
Cross-system canonical entity model for HeyKarl RAG.

Maps system-specific concepts from Salesforce, Jira, Confluence, and SAP
into a unified, auditable knowledge representation.

Canonical Entity Types
----------------------
BusinessObject   → Salesforce Object, Jira Issue, SAP Business Object
Process          → Salesforce Flow, Jira Workflow, SAP Business Process
ProcessStep      → Jira Status/Transition, SAP Activity, Flow Element
Role             → Salesforce Profile, Jira User, SAP Org Unit
Permission       → Salesforce PermissionSet, Jira Permission Scheme, SAP Auth Object
Integration      → Salesforce Named Credential, SAP BAPI/OData, Jira Webhook
API              → REST/SOAP/Bulk/Tooling/Metadata/OData endpoint
Event            → Platform Event, Jira Webhook, SAP BADI/Event
Rule             → Business Rule, Constraint, Validation Rule, SAP Customizing
Capability       → Salesforce Feature, Jira Project, SAP Module, Confluence Space
KnowledgeObject  → Confluence Page/Template
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ── Enumerations ──────────────────────────────────────────────────────────────

CanonicalType = Literal[
    "BusinessObject",
    "Process",
    "ProcessStep",
    "Role",
    "Permission",
    "Integration",
    "API",
    "Event",
    "Rule",
    "Capability",
    "KnowledgeObject",
]

SourceSystem = Literal["salesforce", "jira", "confluence", "sap"]

ChunkType = Literal[
    "object_overview",
    "object_field",
    "process_overview",
    "process_step",
    "workflow",
    "rule",
    "permission",
    "integration_pattern",
    "api_reference",
    "best_practice",
    "constraint",
    "knowledge_object",
    "general",
]

ProcessLevel = Literal["L1", "L2", "L3"]
AuditRelevance = Literal["low", "medium", "high"]
IntegrationRelevance = Literal["low", "medium", "high"]


# ── System-specific → Canonical mapping ──────────────────────────────────────

#: Maps (source_system, system_specific_type) → CanonicalType
SYSTEM_TYPE_MAP: dict[tuple[str, str], CanonicalType] = {
    # Salesforce
    ("salesforce", "object"):           "BusinessObject",
    ("salesforce", "flow"):             "Process",
    ("salesforce", "workflow"):         "Process",
    ("salesforce", "profile"):          "Permission",
    ("salesforce", "permission_set"):   "Permission",
    ("salesforce", "role"):             "Role",
    ("salesforce", "named_credential"): "Integration",
    ("salesforce", "api"):              "API",
    ("salesforce", "platform_event"):   "Event",
    ("salesforce", "validation_rule"):  "Rule",
    ("salesforce", "feature"):          "Capability",

    # Jira
    ("jira", "issue"):             "BusinessObject",
    ("jira", "issue_type"):        "BusinessObject",
    ("jira", "workflow"):          "Process",
    ("jira", "status"):            "ProcessStep",
    ("jira", "transition"):        "ProcessStep",
    ("jira", "user"):              "Role",
    ("jira", "group"):             "Role",
    ("jira", "permission_scheme"): "Permission",
    ("jira", "project_role"):      "Permission",
    ("jira", "webhook"):           "Event",
    ("jira", "automation_rule"):   "Rule",
    ("jira", "project"):           "Capability",
    ("jira", "board"):             "Capability",
    ("jira", "api"):               "API",

    # Confluence
    ("confluence", "page"):      "KnowledgeObject",
    ("confluence", "template"):  "KnowledgeObject",
    ("confluence", "space"):     "Capability",
    ("confluence", "label"):     "Rule",
    ("confluence", "user"):      "Role",
    ("confluence", "group"):     "Permission",
    ("confluence", "api"):       "API",

    # SAP S/4HANA
    ("sap", "business_object"):    "BusinessObject",
    ("sap", "sales_order"):        "BusinessObject",
    ("sap", "purchase_order"):     "BusinessObject",
    ("sap", "business_process"):   "Process",
    ("sap", "process_step"):       "ProcessStep",
    ("sap", "activity"):           "ProcessStep",
    ("sap", "org_unit"):           "Role",
    ("sap", "authorization_object"): "Permission",
    ("sap", "role_concept"):       "Permission",
    ("sap", "bapi"):               "API",
    ("sap", "odata_service"):      "API",
    ("sap", "idoc"):               "Integration",
    ("sap", "badi"):               "Event",
    ("sap", "customizing"):        "Rule",
    ("sap", "module"):             "Capability",
    ("sap", "best_practice"):      "Rule",
}


def resolve_canonical_type(source_system: str, system_type: str) -> CanonicalType:
    """Resolve system-specific type to canonical type. Fallback: 'BusinessObject'."""
    return SYSTEM_TYPE_MAP.get(
        (source_system.lower(), system_type.lower()), "BusinessObject"
    )


# ── Canonical Entity ──────────────────────────────────────────────────────────

@dataclass
class CanonicalEntity:
    name:            str
    canonical_type:  CanonicalType
    source_system:   SourceSystem
    system_type:     str
    attributes:      dict = field(default_factory=dict)
    aliases:         list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name":           self.name,
            "canonical_type": self.canonical_type,
            "source_system":  self.source_system,
            "system_type":    self.system_type,
            "attributes":     self.attributes,
            "aliases":        self.aliases,
        }


# ── Chunk Metadata ────────────────────────────────────────────────────────────

@dataclass
class CanonicalChunkMeta:
    """
    Structured metadata attached to every document chunk.
    Stored in document_chunks.metadata_json (JSONB) or passed as
    source_metadata to ChunkingService.
    """
    source_system:         SourceSystem
    canonical_type:        CanonicalType
    chunk_type:            ChunkType
    entities:              dict                    # output of UniversalEntityExtractor.entities
    capability_candidates: list[str]
    process_candidates:    list[str]
    process_level:         ProcessLevel
    audit_relevance:       AuditRelevance
    integration_relevance: IntegrationRelevance
    vendor:                str = "unknown"
    doc_category:          str = ""
    language:              str = "en"

    def to_dict(self) -> dict:
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
            "vendor":                self.vendor,
            "doc_category":          self.doc_category,
            "language":              self.language,
        }


# ── Process Level Inference ───────────────────────────────────────────────────

def infer_process_level(breadcrumb: list[str], chunk_type: ChunkType) -> ProcessLevel:
    """
    Infer process level from breadcrumb depth and chunk type.

    L1 — capability / module level (top of hierarchy)
    L2 — process / workflow level
    L3 — step / activity / field level
    """
    if chunk_type in ("object_field", "process_step", "constraint"):
        return "L3"
    if chunk_type in ("process_overview", "workflow", "permission"):
        return "L2"
    if len(breadcrumb) >= 3:
        return "L3"
    if len(breadcrumb) == 2:
        return "L2"
    return "L1"
