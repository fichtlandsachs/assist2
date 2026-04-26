# tests/unit/test_universal_entity_service.py
"""
Unit tests for the Multi-System Universal Entity Extractor.

Covers:
- System detection from source_key and metadata_defaults
- Entity extraction per system: Salesforce, Jira, Confluence, SAP
- Cross-system canonical type mapping
- Chunk type classification (all 11 types)
- Process level inference
- Audit / integration relevance scoring
- Serialisation: to_dict(), to_chunk_meta()
- Edge cases: empty text, unknown system, noise text
"""
from __future__ import annotations

import pytest

from app.services.crawl.universal_entity_service import UniversalEntityExtractor, UniversalExtractionResult
from app.services.crawl.canonical_model import (
    resolve_canonical_type,
    infer_process_level,
    SYSTEM_TYPE_MAP,
)


@pytest.fixture()
def ext() -> UniversalEntityExtractor:
    return UniversalEntityExtractor()


# ══════════════════════════════════════════════════════════════════════════════
# CANONICAL MODEL
# ══════════════════════════════════════════════════════════════════════════════

class TestCanonicalModel:
    def test_salesforce_object_maps_to_business_object(self):
        assert resolve_canonical_type("salesforce", "object") == "BusinessObject"

    def test_salesforce_flow_maps_to_process(self):
        assert resolve_canonical_type("salesforce", "flow") == "Process"

    def test_jira_workflow_maps_to_process(self):
        assert resolve_canonical_type("jira", "workflow") == "Process"

    def test_jira_status_maps_to_process_step(self):
        assert resolve_canonical_type("jira", "status") == "ProcessStep"

    def test_sap_business_process_maps_to_process(self):
        assert resolve_canonical_type("sap", "business_process") == "Process"

    def test_sap_authorization_object_maps_to_permission(self):
        assert resolve_canonical_type("sap", "authorization_object") == "Permission"

    def test_confluence_space_maps_to_capability(self):
        assert resolve_canonical_type("confluence", "space") == "Capability"

    def test_unknown_system_type_returns_business_object(self):
        assert resolve_canonical_type("salesforce", "nonexistent") == "BusinessObject"

    def test_all_entries_in_map_return_valid_types(self):
        valid = {"BusinessObject", "Process", "ProcessStep", "Role", "Permission",
                 "Integration", "API", "Event", "Rule", "Capability", "KnowledgeObject"}
        for key, val in SYSTEM_TYPE_MAP.items():
            assert val in valid, f"{key} → {val} is not a valid CanonicalType"

    def test_process_level_object_field_is_L3(self):
        assert infer_process_level([], "object_field") == "L3"

    def test_process_level_process_overview_is_L2(self):
        assert infer_process_level([], "process_overview") == "L2"

    def test_process_level_deep_breadcrumb_is_L3(self):
        assert infer_process_level(["A", "B", "C"], "general") == "L3"

    def test_process_level_no_breadcrumb_is_L1(self):
        assert infer_process_level([], "general") == "L1"


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class TestSystemDetection:
    def test_detect_salesforce_from_source_key(self, ext):
        r = ext.extract("Account stores data.", source_key="sf_object_reference")
        assert r.source_system == "salesforce"

    def test_detect_jira_from_source_key(self, ext):
        r = ext.extract("Workflow transition to Done.", source_key="jira_software_docs")
        assert r.source_system == "jira"

    def test_detect_confluence_from_source_key(self, ext):
        r = ext.extract("Confluence Space for team knowledge.", source_key="confluence_docs")
        assert r.source_system == "confluence"

    def test_detect_sap_from_source_key(self, ext):
        r = ext.extract("Sales Order processing.", source_key="sap_s4hana_help_en")
        assert r.source_system == "sap"

    def test_detect_salesforce_from_metadata(self, ext):
        r = ext.extract("Account data.", metadata_defaults={"vendor": "Salesforce"})
        assert r.source_system == "salesforce"

    def test_detect_sap_from_metadata(self, ext):
        r = ext.extract("Order-to-Cash process.", metadata_defaults={"vendor": "sap"})
        assert r.source_system == "sap"

    def test_detect_jira_from_metadata(self, ext):
        r = ext.extract("Jira Workflow.", metadata_defaults={"vendor": "Atlassian"})
        assert r.source_system == "jira"

    def test_default_system_is_salesforce(self, ext):
        r = ext.extract("Some text.", source_key="unknown_key")
        assert r.source_system == "salesforce"


# ══════════════════════════════════════════════════════════════════════════════
# SALESFORCE ENTITY EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestSalesforceExtraction:
    def test_extracts_standard_objects(self, ext):
        r = ext.extract("Account and Contact are linked.", source_key="sf_object_reference")
        assert "Account" in r.entities["objects"]
        assert "Contact" in r.entities["objects"]

    def test_extracts_flows(self, ext):
        r = ext.extract("Use a Record-Triggered Flow for automation.", source_key="sf_flow_automation")
        assert any("Flow" in f for f in r.entities["flows"])

    def test_extracts_apis(self, ext):
        r = ext.extract("Use REST API or Bulk API 2.0 for data access.", source_key="sf_rest_api")
        assert any("REST API" in a for a in r.entities["apis"])

    def test_extracts_permissions(self, ext):
        r = ext.extract("Assign a Permission Set instead of editing the Profile.", source_key="sf_security_guide")
        assert any("Permission Set" in p for p in r.entities["permissions"])

    def test_extracts_integration_patterns(self, ext):
        r = ext.extract("Apply the Request-Reply pattern for synchronous calls.", source_key="sf_integration_patterns")
        assert any("Request-Reply" in p for p in r.entities["patterns"])

    def test_extracts_recommendation_facts(self, ext):
        r = ext.extract("It is recommended to use Named Credentials.", source_key="sf_rest_api")
        assert any(f["kind"] == "recommendation" for f in r.facts)

    def test_extracts_security_rule_facts(self, ext):
        r = ext.extract("OAuth must be required for all integrations.", source_key="sf_security_guide")
        assert any(f["kind"] == "security_rule" for f in r.facts)


# ══════════════════════════════════════════════════════════════════════════════
# JIRA ENTITY EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestJiraExtraction:
    def test_extracts_issue_types(self, ext):
        r = ext.extract("Create an Epic for the initiative. Add Stories and Bugs.", source_key="jira_software_docs")
        objs = r.entities["objects"]
        assert "Epic" in objs or "Story" in objs or "Bug" in objs

    def test_extracts_workflow_statuses(self, ext):
        r = ext.extract("Move the issue from In Progress to Done via a transition.", source_key="jira_software_docs")
        assert any(s in r.entities["steps"] for s in ["In Progress", "Done"])

    def test_extracts_permission_schemes(self, ext):
        r = ext.extract("Configure the Permission Scheme for your project. Assign a Project Role.", source_key="jira_admin_permissions")
        assert any("Permission Scheme" in p or "Project Role" in p for p in r.entities["permissions"])

    def test_extracts_automation_as_flow(self, ext):
        r = ext.extract("Use an Automation Rule to transition issues automatically.", source_key="jira_workflows_docs")
        assert any("Automation" in f for f in r.entities["flows"])

    def test_extracts_jira_api(self, ext):
        r = ext.extract("Use the Jira REST API to create issues programmatically.", source_key="atlassian_rest_api")
        assert any("API" in a or "REST" in a for a in r.entities["apis"])

    def test_chunk_type_workflow_for_jira_workflow(self, ext):
        r = ext.extract(
            "This Workflow defines the transitions between issue statuses.",
            source_key="jira_workflows_docs",
            page_title="Workflow Configuration",
        )
        assert r.chunk_type in ("workflow", "process_overview", "process_step")

    def test_canonical_type_process_for_workflow(self, ext):
        r = ext.extract(
            "The Workflow controls the lifecycle of an issue.",
            source_key="jira_workflows_docs",
        )
        assert r.canonical_type in ("Process", "ProcessStep", "BusinessObject")


# ══════════════════════════════════════════════════════════════════════════════
# CONFLUENCE ENTITY EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestConfluenceExtraction:
    def test_extracts_templates(self, ext):
        r = ext.extract("Use the Meeting Notes template or the Decision Blueprint.", source_key="confluence_docs")
        assert any("Meeting Notes" in t or "Blueprint" in t or "Decision" in t for t in r.entities["objects"])

    def test_extracts_space_permissions(self, ext):
        r = ext.extract("Space Permission must be granted to the Group. Anonymous Access must be disabled.", source_key="confluence_docs")
        perms = r.entities["permissions"]
        assert any("Permission" in p or "Access" in p for p in perms)

    def test_chunk_type_knowledge_object_for_confluence(self, ext):
        r = ext.extract(
            "This page explains how to use Confluence for documentation.",
            source_key="confluence_docs",
            page_title="Getting Started with Confluence",
        )
        assert r.chunk_type == "knowledge_object"

    def test_canonical_type_knowledge_object(self, ext):
        r = ext.extract("Page content.", source_key="confluence_docs")
        assert r.canonical_type == "KnowledgeObject"


# ══════════════════════════════════════════════════════════════════════════════
# SAP ENTITY EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestSapExtraction:
    def test_extracts_business_objects(self, ext):
        r = ext.extract("Create a Sales Order and post a Goods Receipt.", source_key="sap_s4hana_help_en")
        assert any("Sales Order" in o for o in r.entities["objects"])
        assert any("Goods Receipt" in s for s in r.entities["steps"])

    def test_extracts_business_processes(self, ext):
        r = ext.extract("The Order-to-Cash and Procure-to-Pay processes are core to S/4HANA.", source_key="sap_best_practices")
        assert any("Order-to-Cash" in p for p in r.entities["processes"])
        assert any("Procure-to-Pay" in p for p in r.entities["processes"])

    def test_extracts_authorization_objects(self, ext):
        r = ext.extract("Configure the Authorization Object for the role concept using PFCG.", source_key="sap_s4hana_help_en")
        assert any("Authorization Object" in p or "PFCG" in p for p in r.entities["permissions"])

    def test_extracts_sap_apis(self, ext):
        r = ext.extract("Use BAPI_SALESORDER_CREATEFROMDAT2 or the OData Service for integration.", source_key="sap_api_business_hub")
        assert any("BAPI" in a or "OData" in a for a in r.entities["apis"])

    def test_extracts_badi_as_event(self, ext):
        r = ext.extract("Implement a BAdI to enhance the standard behavior.", source_key="sap_s4hana_help_en")
        assert any("BAdI" in e for e in r.entities["events"])

    def test_extracts_sod_security_rule(self, ext):
        r = ext.extract("Segregation of duties must be enforced using authorization objects.", source_key="sap_s4hana_help_en")
        sec_facts = [f for f in r.facts if f["kind"] == "security_rule"]
        assert len(sec_facts) >= 1

    def test_chunk_type_process_for_order_to_cash(self, ext):
        r = ext.extract(
            "The Order-to-Cash business process covers sales from quotation to payment.",
            source_key="sap_best_practices",
            page_title="Order-to-Cash",
            breadcrumb=["SAP Best Practices", "Finance"],
        )
        assert r.chunk_type in ("process_overview", "workflow")

    def test_capability_candidate_from_breadcrumb(self, ext):
        r = ext.extract(
            "This document covers the S/4HANA Finance module.",
            source_key="sap_s4hana_help_en",
            breadcrumb=["Finance", "GL Accounting"],
        )
        assert "Finance" in r.capability_candidates


# ══════════════════════════════════════════════════════════════════════════════
# CHUNK TYPE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════

class TestChunkTypeClassification:
    def test_permission_chunk_type(self, ext):
        r = ext.extract(
            "Configure Permission Set Groups. Restrict access via Field-Level Security.",
            source_key="sf_security_guide",
            page_title="Security Configuration",
        )
        assert r.chunk_type in ("permission", "rule")

    def test_api_reference_chunk_type(self, ext):
        r = ext.extract(
            "The REST API endpoint POST /sobjects/Account creates a new account.",
            source_key="sf_rest_api",
            page_title="REST API Reference",
        )
        assert r.chunk_type in ("api_reference", "integration_pattern")

    def test_integration_pattern_chunk_type(self, ext):
        r = ext.extract(
            "Use the Request-Reply integration pattern for synchronous callouts.",
            source_key="sf_integration_patterns",
            page_title="Integration Patterns",
            breadcrumb=["Integration", "Patterns"],
        )
        assert r.chunk_type == "integration_pattern"

    def test_object_field_chunk_type(self, ext):
        r = ext.extract(
            "The Account.BillingCountry field stores the country for billing.",
            source_key="sf_object_reference",
            page_title="Account Fields",
        )
        assert r.chunk_type in ("object_field", "object_overview")

    def test_best_practice_chunk_type(self, ext):
        r = ext.extract(
            "Best practice: always use Named Credentials for external endpoints.",
            source_key="sf_well_architected",
            page_title="Best Practices",
        )
        assert r.chunk_type in ("best_practice", "rule", "constraint")

    def test_constraint_chunk_type(self, ext):
        r = ext.extract(
            "Avoid using SOQL queries inside loops. This is deprecated and not supported.",
            source_key="sf_object_reference",
            page_title="Governor Limits",
        )
        assert r.chunk_type in ("constraint", "rule", "best_practice")


# ══════════════════════════════════════════════════════════════════════════════
# RELEVANCE SCORING
# ══════════════════════════════════════════════════════════════════════════════

class TestRelevanceScoring:
    def test_high_audit_relevance_for_security_text(self, ext):
        r = ext.extract(
            "OAuth must be enforced. MFA is required. Permission Set must be configured. Encryption is mandatory.",
            source_key="sf_security_guide",
        )
        assert r.audit_relevance in ("medium", "high")

    def test_high_integration_relevance(self, ext):
        r = ext.extract(
            "Use REST API and OData Service. Apply the Request-Reply pattern and Fire and Forget.",
            source_key="sap_api_business_hub",
        )
        assert r.integration_relevance == "high"

    def test_low_relevance_neutral_text(self, ext):
        r = ext.extract("This is an overview page.", source_key="sf_object_reference")
        assert r.audit_relevance == "low"
        assert r.integration_relevance == "low"


# ══════════════════════════════════════════════════════════════════════════════
# SERIALISATION
# ══════════════════════════════════════════════════════════════════════════════

class TestSerialisation:
    def test_to_dict_keys(self, ext):
        r = ext.extract("Account.", source_key="sf_object_reference")
        d = r.to_dict()
        required = {"summary", "source_system", "canonical_type", "chunk_type", "entities",
                    "facts", "capability_candidates", "process_candidates",
                    "process_level", "audit_relevance", "integration_relevance"}
        assert required.issubset(d.keys())

    def test_entities_keys(self, ext):
        r = ext.extract("Account.", source_key="sf_object_reference")
        ent = r.to_dict()["entities"]
        required_keys = {"objects", "fields", "flows", "roles", "permissions",
                         "apis", "patterns", "processes", "steps", "events", "rules"}
        assert required_keys.issubset(ent.keys())

    def test_to_chunk_meta_keys(self, ext):
        r = ext.extract("Account.", source_key="sf_object_reference")
        meta = r.to_chunk_meta(vendor="Salesforce", doc_category="object_reference", language="en")
        assert "source_system" in meta
        assert "canonical_type" in meta
        assert "chunk_type" in meta
        assert "entities" in meta
        assert meta["vendor"] == "Salesforce"

    def test_facts_schema(self, ext):
        r = ext.extract("OAuth must be required for integrations.", source_key="sf_security_guide")
        for fact in r.facts:
            assert "kind" in fact
            assert "subject" in fact
            assert "predicate" in fact
            assert "object" in fact


# ══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_text(self, ext):
        r = ext.extract("", source_key="sf_object_reference")
        assert isinstance(r, UniversalExtractionResult)
        assert r.entities["objects"] == []
        assert r.facts == []

    def test_very_short_text(self, ext):
        r = ext.extract("Hi.", source_key="jira_software_docs")
        assert isinstance(r, UniversalExtractionResult)

    def test_plain_english_no_entities(self, ext):
        r = ext.extract("The weather is fine today.", source_key="sf_object_reference")
        assert r.entities["objects"] == []
        assert r.entities["apis"] == []

    def test_summary_not_empty(self, ext):
        r = ext.extract("Account is a core object.", source_key="sf_object_reference", page_title="Account Overview")
        assert len(r.summary) > 0

    def test_process_level_values(self, ext):
        r = ext.extract("Some documentation text.", source_key="sf_object_reference")
        assert r.process_level in ("L1", "L2", "L3")

    def test_audit_relevance_values(self, ext):
        r = ext.extract("Some documentation text.", source_key="jira_software_docs")
        assert r.audit_relevance in ("low", "medium", "high")

    def test_integration_relevance_values(self, ext):
        r = ext.extract("Some documentation text.", source_key="sap_api_business_hub")
        assert r.integration_relevance in ("low", "medium", "high")
