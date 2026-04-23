"""Unit tests for URL canonicalization."""
import pytest

from app.services.crawl.url_canonicalizer import UrlCanonicalizer

BASE_PREFIX = "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/"

REQUIRED_PARAMS = {"locale": "en-US", "state": "PRODUCTION", "version": "2025.001"}
DROPPED_PARAMS = {"q", "search", "sort", "page"}
ALLOWED_DOMAINS = ["help.sap.com"]
ALLOWED_PREFIXES = [BASE_PREFIX]


@pytest.fixture
def canon():
    return UrlCanonicalizer(
        required_params=REQUIRED_PARAMS,
        dropped_params=DROPPED_PARAMS,
        allowed_prefixes=ALLOWED_PREFIXES,
        allowed_domains=ALLOWED_DOMAINS,
    )


def test_drops_q_param(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=utilities"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "q=" not in result


def test_preserves_required_params(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "locale=en-US" in result
    assert "state=PRODUCTION" in result
    assert "version=2025.001" in result


def test_adds_missing_required_params(canon):
    raw = BASE_PREFIX + "page.html"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "locale=en-US" in result
    assert "state=PRODUCTION" in result


def test_removes_fragment(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001#section-1"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "#" not in result


def test_rejects_wrong_domain(canon):
    raw = "https://example.com/page"
    result = canon.canonicalize(raw)
    assert result is None


def test_rejects_other_sap_collection(canon):
    raw = "https://help.sap.com/docs/OTHER_PRODUCT/different_collection/page.html?locale=en-US&state=PRODUCTION&version=2025.001"
    in_scope, _ = canon.is_in_scope(raw)
    assert not in_scope


def test_duplicate_urls_converge(canon):
    raw1 = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=alpha"
    raw2 = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=beta"
    c1 = canon.canonicalize(raw1)
    c2 = canon.canonicalize(raw2)
    assert c1 == c2


def test_params_sorted_deterministically(canon):
    raw1 = BASE_PREFIX + "page.html?version=2025.001&locale=en-US&state=PRODUCTION"
    raw2 = BASE_PREFIX + "page.html?state=PRODUCTION&version=2025.001&locale=en-US"
    assert canon.canonicalize(raw1) == canon.canonicalize(raw2)


def test_drops_utm_params(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&utm_source=email"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "utm_" not in result


def test_is_in_scope_returns_canonical(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=x"
    in_scope, canonical = canon.is_in_scope(raw)
    assert in_scope
    assert canonical is not None
    assert "q=" not in canonical
