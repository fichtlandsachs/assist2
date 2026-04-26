# tests/unit/test_workspace_response_service.py
"""
Unit tests for WorkspaceResponseService and HybridRetrievalResult.

Covers:
- No-evidence response (guardrail = 'no_evidence')
- Security guardrail: query needs security evidence, none present
- Pattern guardrail: query needs integration evidence, none present
- Full response: entity merging, role deduplication, evidence refs
- Confidence scaling
- to_dict() schema compliance
- to_prompt_context() format
- format_no_evidence_message()
- top_source_systems() ordering
- entities_union() merging
"""
from __future__ import annotations

import pytest

from app.services.hybrid_retrieval_service import HybridChunk, HybridRetrievalResult
from app.services.workspace_response_service import WorkspaceResponseService


def _make_chunk(**kwargs) -> HybridChunk:
    defaults = dict(
        text="This is a documentation chunk.",
        semantic_score=0.80,
        bm25_score=0.50,
        final_score=0.42,
        source_system="salesforce",
        source_type="external_docs",
        source_url="https://developer.salesforce.com/docs/example",
        source_title="Account Object Reference",
        chunk_type="object_overview",
        canonical_type="BusinessObject",
        entities={
            "objects": ["Account"],
            "fields": ["Account.BillingCountry"],
            "flows": [],
            "roles": ["Profile"],
            "permissions": ["Permission Set"],
            "apis": ["REST API"],
            "patterns": [],
            "processes": [],
            "steps": [],
            "events": [],
            "rules": ["Avoid SOQL in loops."],
            "facts": [
                {"kind": "constraint", "subject": "Account", "predicate": "constraint", "object": "Avoid SOQL in loops."}
            ],
        },
        indexed_at="2025-01-01T00:00:00+00:00",
        is_global=True,
    )
    defaults.update(kwargs)
    return HybridChunk(**defaults)


@pytest.fixture()
def svc() -> WorkspaceResponseService:
    return WorkspaceResponseService()


# ── No evidence ───────────────────────────────────────────────────────────────

class TestNoEvidenceResponse:
    def test_empty_result_returns_no_evidence(self, svc):
        result = HybridRetrievalResult(mode="none", chunks=[])
        resp = svc.build("What is Account?", result)
        assert resp.guardrail == "no_evidence"
        assert resp.confidence == 0.0
        assert resp.objects == []
        assert resp.evidence == []

    def test_no_evidence_message_contains_query(self, svc):
        msg = svc.format_no_evidence_message("Account object fields")
        assert "Account object fields" in msg
        assert "offiziellen" in msg


# ── Guardrail checks ─────────────────────────────────────────────────────────

class TestGuardrails:
    def test_security_guardrail_when_no_permission_evidence(self, svc):
        chunk = _make_chunk(
            chunk_type="object_overview",
            entities={
                "objects": ["Account"], "fields": [], "flows": [], "roles": [],
                "permissions": [], "apis": [], "patterns": [], "processes": [],
                "steps": [], "events": [], "rules": [], "facts": [],
            }
        )
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What are the security permissions for Account?", result)
        assert resp.guardrail == "insufficient_security"

    def test_pattern_guardrail_when_no_integration_evidence(self, svc):
        chunk = _make_chunk(
            chunk_type="object_overview",
            entities={
                "objects": ["Contact"], "fields": [], "flows": [], "roles": [],
                "permissions": [], "apis": [], "patterns": [], "processes": [],
                "steps": [], "events": [], "rules": [], "facts": [],
            }
        )
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What integration patterns should I use for the API?", result)
        assert resp.guardrail == "insufficient_pattern"

    def test_ok_guardrail_when_permission_evidence_present(self, svc):
        chunk = _make_chunk(chunk_type="permission")
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What security permissions are needed?", result)
        assert resp.guardrail == "ok"

    def test_ok_guardrail_for_neutral_query(self, svc):
        chunk = _make_chunk()
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What is the Account object?", result)
        assert resp.guardrail == "ok"


# ── Entity merging ────────────────────────────────────────────────────────────

class TestEntityMerging:
    def test_objects_merged_from_multiple_chunks(self, svc):
        c1 = _make_chunk(entities={**_make_chunk().entities, "objects": ["Account"]})
        c2 = _make_chunk(entities={**_make_chunk().entities, "objects": ["Contact", "Lead"]})
        result = HybridRetrievalResult(mode="context", chunks=[c1, c2])
        resp = svc.build("Tell me about objects.", result)
        assert "Account" in resp.objects
        assert "Contact" in resp.objects

    def test_roles_deduplicated(self, svc):
        chunk = _make_chunk(entities={
            **_make_chunk().entities,
            "roles": ["Profile", "Profile"],
            "permissions": ["Permission Set", "Permission Set"],
        })
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What roles are involved?", result)
        assert resp.roles.count("Profile") == 1

    def test_integration_includes_apis_and_patterns(self, svc):
        chunk = _make_chunk(entities={
            **_make_chunk().entities,
            "apis": ["REST API"],
            "patterns": ["Request-Reply"],
            "events": ["Platform Event"],
        })
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("How to integrate?", result)
        assert "REST API" in resp.integration
        assert "Request-Reply" in resp.integration

    def test_rules_extracted_from_facts(self, svc):
        chunk = _make_chunk(entities={
            **_make_chunk().entities,
            "rules": [],
            "facts": [{"kind": "constraint", "subject": "Account", "predicate": "constraint", "object": "Avoid SOQL in loops."}],
        })
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("What are the constraints?", result)
        assert any("SOQL" in r for r in resp.rules)


# ── Evidence references ───────────────────────────────────────────────────────

class TestEvidenceRefs:
    def test_evidence_refs_present(self, svc):
        chunk = _make_chunk()
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("Account object?", result)
        assert len(resp.evidence) == 1
        ev = resp.evidence[0]
        assert ev.source_system == "salesforce"
        assert ev.source_url is not None
        assert ev.chunk_type == "object_overview"

    def test_evidence_refs_capped_at_8(self, svc):
        chunks = [_make_chunk(source_url=f"https://example.com/{i}") for i in range(12)]
        result = HybridRetrievalResult(mode="context", chunks=chunks)
        resp = svc.build("Account?", result)
        assert len(resp.evidence) <= 8

    def test_evidence_to_dict(self, svc):
        chunk = _make_chunk()
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("Account?", result)
        ev_dict = resp.evidence[0].to_dict()
        assert set(ev_dict.keys()) == {"source_system", "source_url", "source_title", "chunk_type", "relevance", "excerpt"}


# ── Source systems ────────────────────────────────────────────────────────────

class TestSourceSystems:
    def test_source_systems_from_chunks(self, svc):
        c1 = _make_chunk(source_system="salesforce", final_score=0.5)
        c2 = _make_chunk(source_system="sap", final_score=0.4)
        result = HybridRetrievalResult(mode="context", chunks=[c1, c2])
        resp = svc.build("Query?", result)
        assert "salesforce" in resp.source_systems

    def test_top_source_systems_ordered_by_score(self):
        c1 = HybridChunk(
            text="x", semantic_score=0.9, bm25_score=0.5, final_score=0.9,
            source_system="sap", source_type="external_docs", source_url=None,
            source_title=None, chunk_type="general", canonical_type="",
            entities={}, is_global=True,
        )
        c2 = HybridChunk(
            text="y", semantic_score=0.5, bm25_score=0.3, final_score=0.3,
            source_system="jira", source_type="external_docs", source_url=None,
            source_title=None, chunk_type="general", canonical_type="",
            entities={}, is_global=True,
        )
        result = HybridRetrievalResult(mode="context", chunks=[c1, c2])
        systems = result.top_source_systems()
        assert systems[0] == "sap"

    def test_entities_union_merges_all_chunks(self):
        c1 = HybridChunk(
            text="x", semantic_score=0.8, bm25_score=0.5, final_score=0.4,
            source_system="salesforce", source_type="external_docs", source_url=None,
            source_title=None, chunk_type="general", canonical_type="",
            entities={"objects": ["Account"], "apis": ["REST API"]}, is_global=True,
        )
        c2 = HybridChunk(
            text="y", semantic_score=0.7, bm25_score=0.4, final_score=0.3,
            source_system="sap", source_type="external_docs", source_url=None,
            source_title=None, chunk_type="general", canonical_type="",
            entities={"objects": ["Sales Order"], "apis": ["OData Service"]}, is_global=True,
        )
        result = HybridRetrievalResult(mode="context", chunks=[c1, c2])
        union = result.entities_union()
        assert "Account" in union.get("objects", [])
        assert "Sales Order" in union.get("objects", [])


# ── Output serialisation ─────────────────────────────────────────────────────

class TestOutputSerialisation:
    def test_to_dict_schema(self, svc):
        chunk = _make_chunk()
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("Account?", result)
        d = resp.to_dict()
        required = {"capability", "process", "objects", "roles", "rules",
                    "integration", "source_systems", "evidence", "guardrail", "confidence"}
        assert required == set(d.keys())

    def test_confidence_between_0_and_1(self, svc):
        chunk = _make_chunk(final_score=0.8)
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("Account?", result)
        assert 0.0 <= resp.confidence <= 1.0

    def test_to_prompt_context_contains_sections(self, svc):
        chunk = _make_chunk()
        result = HybridRetrievalResult(mode="context", chunks=[chunk])
        resp = svc.build("Account object?", result)
        ctx = resp.to_prompt_context()
        assert "WORKSPACE CONTEXT" in ctx
        assert "Evidence:" in ctx
        assert "END CONTEXT" in ctx

    def test_guardrail_in_to_dict(self, svc):
        result = HybridRetrievalResult(mode="none", chunks=[])
        resp = svc.build("test", result)
        assert resp.to_dict()["guardrail"] == "no_evidence"
