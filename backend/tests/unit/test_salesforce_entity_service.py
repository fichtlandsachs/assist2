# tests/unit/test_salesforce_entity_service.py
"""Unit tests for the Salesforce entity extractor.

Covers:
- Entity extraction (objects, fields, flows, roles, permissions, apis, patterns)
- Fact extraction (recommendation, constraint, security_rule)
- Chunk classification
- Relevance scoring
- Serialisation to dict (JSON schema compliance)
- Edge cases (empty text, no entities, noise)
"""
from __future__ import annotations

import pytest

from app.services.crawl.salesforce_entity_service import (
    SalesforceEntityExtractor,
    SalesforceExtractionResult,
)


@pytest.fixture()
def extractor() -> SalesforceEntityExtractor:
    return SalesforceEntityExtractor()


# ── Entity extraction ─────────────────────────────────────────────────────────

class TestEntityExtraction:
    def test_extracts_standard_objects(self, extractor):
        text = "The Account object stores customer data. Contact records link to Account."
        result = extractor.extract(text)
        assert "Account" in result.entities.objects
        assert "Contact" in result.entities.objects

    def test_extracts_custom_objects(self, extractor):
        text = "Use MyCustomObject__c to store project data. Invoice__mdt holds tax rules."
        result = extractor.extract(text)
        assert "MyCustomObject__c" in result.entities.objects
        assert "Invoice__mdt" in result.entities.objects

    def test_extracts_object_field_pairs(self, extractor):
        text = "Set Account.BillingCountry and Contact.Email to ensure data quality."
        result = extractor.extract(text)
        assert "Account.BillingCountry" in result.entities.fields
        assert "Contact.Email" in result.entities.fields

    def test_no_common_words_as_objects(self, extractor):
        text = "The system is running. Users are logged in. Data is processed."
        result = extractor.extract(text)
        # "The", "Users", "Data" should NOT appear as Salesforce objects
        assert "The" not in result.entities.objects
        assert "Data" not in result.entities.objects

    def test_extracts_flows(self, extractor):
        text = "Use a Record-Triggered Flow instead of a Workflow Rule. Platform Event triggers are supported."
        result = extractor.extract(text)
        assert any("Flow" in f for f in result.entities.flows)
        assert any("Platform Event" in f for f in result.entities.flows)

    def test_extracts_apis(self, extractor):
        text = "Use the REST API for real-time operations and Bulk API 2.0 for large data loads."
        result = extractor.extract(text)
        assert any("REST API" in a for a in result.entities.apis)
        assert any("Bulk API" in a for a in result.entities.apis)

    def test_extracts_integration_patterns(self, extractor):
        text = "The Request-Reply pattern is recommended for synchronous callouts. Fire and Forget works for async."
        result = extractor.extract(text)
        assert any("Request-Reply" in p for p in result.entities.patterns)
        assert any("Fire and Forget" in p for p in result.entities.patterns)

    def test_extracts_permissions(self, extractor):
        text = "Assign a Permission Set to users instead of modifying the System Administrator profile."
        result = extractor.extract(text)
        assert any("Permission Set" in p for p in result.entities.permissions)

    def test_extracts_roles(self, extractor):
        text = "Configure Field-Level Security on the Profile. Use Role Hierarchy to control record visibility."
        result = extractor.extract(text)
        assert any("Field-Level Security" in r for r in result.entities.roles)


# ── Fact extraction ───────────────────────────────────────────────────────────

class TestFactExtraction:
    def test_recommendation_fact(self, extractor):
        text = "It is recommended to use Named Credentials for storing endpoint URLs securely."
        result = extractor.extract(text)
        recs = [f for f in result.facts if f.kind == "recommendation"]
        assert len(recs) >= 1
        assert "Named Credential" in recs[0].object or "recommended" in recs[0].object.lower()

    def test_constraint_fact(self, extractor):
        text = "Avoid using SOQL queries inside loops. This is a known anti-pattern and must be avoided."
        result = extractor.extract(text)
        constraints = [f for f in result.facts if f.kind == "constraint"]
        assert len(constraints) >= 1

    def test_security_rule_fact(self, extractor):
        text = "OAuth 2.0 is required for all external integrations. MFA must be enforced for admin users."
        result = extractor.extract(text)
        sec_rules = [f for f in result.facts if f.kind == "security_rule"]
        assert len(sec_rules) >= 1

    def test_facts_capped_at_30(self, extractor):
        # Generate lots of normative sentences
        sentences = ["You should use REST API. " * 50]
        result = extractor.extract(" ".join(sentences))
        assert len(result.facts) <= 30

    def test_no_facts_for_neutral_text(self, extractor):
        text = "Salesforce is a CRM platform. It stores customer data."
        result = extractor.extract(text)
        # No normative language → no facts (or very few)
        assert len(result.facts) == 0


# ── Chunk classification ──────────────────────────────────────────────────────

class TestChunkClassification:
    def test_classifies_security(self, extractor):
        result = extractor.extract(
            "OAuth 2.0 authentication is required. MFA encryption protects admin accounts.",
            page_title="Security Guide",
        )
        assert result.chunk_type == "security"

    def test_classifies_integration(self, extractor):
        result = extractor.extract(
            "Use the Request-Reply integration pattern for synchronous API callouts.",
            page_title="Integration Patterns",
            breadcrumb=["Integration", "API Patterns"],
        )
        assert result.chunk_type == "integration"

    def test_classifies_automation(self, extractor):
        result = extractor.extract(
            "A Record-Triggered Flow fires when a record is created or updated.",
            page_title="Flow Reference",
        )
        assert result.chunk_type == "automation"

    def test_classifies_object_reference(self, extractor):
        result = extractor.extract(
            "The Account object contains fields like BillingCountry and Industry.",
            page_title="Account Object Reference",
            breadcrumb=["Object Reference", "Standard Objects"],
        )
        assert result.chunk_type == "object_reference"

    def test_classifies_general_fallback(self, extractor):
        result = extractor.extract(
            "Salesforce is a cloud-based CRM.",
            page_title="Overview",
        )
        assert result.chunk_type == "general"


# ── Relevance scoring ─────────────────────────────────────────────────────────

class TestRelevanceScoring:
    def test_high_audit_relevance_for_security_text(self, extractor):
        text = (
            "OAuth must be required. MFA must be enforced. "
            "Encrypt all data at rest. Permission Set must be assigned. "
            "System Administrator profile must be restricted."
        )
        result = extractor.extract(text)
        assert result.audit_relevance in ("medium", "high")

    def test_high_integration_relevance(self, extractor):
        text = (
            "Use REST API and Bulk API 2.0. Apply the Request-Reply pattern. "
            "Fire and Forget is suitable for async operations via Platform Events."
        )
        result = extractor.extract(text, source_key="sf_integration_patterns")
        assert result.integration_relevance == "high"

    def test_low_relevance_for_generic_text(self, extractor):
        result = extractor.extract("Salesforce is a CRM platform used by many companies.")
        assert result.audit_relevance == "low"
        assert result.integration_relevance == "low"


# ── Serialisation ─────────────────────────────────────────────────────────────

class TestSerialisation:
    def test_to_dict_has_required_keys(self, extractor):
        result = extractor.extract("Account stores customer data. REST API is recommended.")
        d = result.to_dict()
        assert set(d.keys()) == {
            "summary", "chunk_type", "entities", "facts",
            "capability_candidates", "process_candidates",
            "audit_relevance", "integration_relevance",
        }

    def test_entities_has_required_keys(self, extractor):
        result = extractor.extract("Account stores customer data.")
        ent = result.to_dict()["entities"]
        assert set(ent.keys()) == {
            "objects", "fields", "flows", "roles", "permissions", "apis", "patterns"
        }

    def test_facts_schema(self, extractor):
        text = "It is recommended to use Named Credentials."
        result = extractor.extract(text)
        for fact in result.to_dict()["facts"]:
            assert set(fact.keys()) == {"kind", "subject", "predicate", "object"}
            assert fact["kind"] in ("definition", "recommendation", "constraint", "security_rule", "integration_rule")

    def test_audit_relevance_values(self, extractor):
        result = extractor.extract("Some text.")
        assert result.to_dict()["audit_relevance"] in ("low", "medium", "high")

    def test_integration_relevance_values(self, extractor):
        result = extractor.extract("Some text.")
        assert result.to_dict()["integration_relevance"] in ("low", "medium", "high")


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text(self, extractor):
        result = extractor.extract("")
        assert isinstance(result, SalesforceExtractionResult)
        assert result.entities.objects == []
        assert result.facts == []

    def test_very_short_text(self, extractor):
        result = extractor.extract("Hi.")
        assert isinstance(result, SalesforceExtractionResult)

    def test_no_sf_entities_in_plain_english(self, extractor):
        text = "The weather is nice today. We went to the market."
        result = extractor.extract(text)
        assert result.entities.objects == []
        assert result.entities.apis == []

    def test_summary_not_empty(self, extractor):
        result = extractor.extract("Account is a standard object.", page_title="Account Reference")
        assert len(result.summary) > 0

    def test_capability_candidates_from_breadcrumb(self, extractor):
        result = extractor.extract(
            "REST API overview.",
            page_title="REST API",
            breadcrumb=["APIs and Integration", "REST"],
        )
        assert "APIs and Integration" in result.capability_candidates

    def test_deduplication_in_entities(self, extractor):
        text = "Account Account Account Contact Contact"
        result = extractor.extract(text)
        assert result.entities.objects.count("Account") == 1
