"""Unit tests for the GlobalConfig model."""
import pytest
from app.models.global_config import GlobalConfig, ALLOWED_KEYS, SECRET_KEYS


def test_allowed_keys_contains_all_tools():
    expected = {
        "litellm.url", "litellm.api_key",
        "nextcloud.url", "nextcloud.admin_user", "nextcloud.admin_password",
        "n8n.url", "n8n.api_key",
        "atlassian.sso_enabled", "atlassian.client_id", "atlassian.client_secret",
        "github.sso_enabled", "github.client_id", "github.client_secret",
        "ai.anthropic_api_key", "ai.openai_api_key", "ai.ionos_api_key",
    }
    assert expected == ALLOWED_KEYS


def test_secret_keys_are_subset_of_allowed():
    assert SECRET_KEYS.issubset(ALLOWED_KEYS)


def test_secret_keys_contains_sensitive_fields():
    assert "litellm.api_key" in SECRET_KEYS
    assert "nextcloud.admin_password" in SECRET_KEYS
    assert "atlassian.client_secret" in SECRET_KEYS
    assert "github.client_secret" in SECRET_KEYS
    assert "ai.anthropic_api_key" in SECRET_KEYS
    assert "litellm.url" not in SECRET_KEYS
    assert "nextcloud.admin_user" not in SECRET_KEYS


def test_global_config_tablename():
    assert GlobalConfig.__tablename__ == "global_config"
