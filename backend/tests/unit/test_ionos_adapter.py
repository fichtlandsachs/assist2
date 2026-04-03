"""Tests for the IONOS provider adapter and routing matrix."""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ── IONOSAdapter.list_models ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_models_returns_ids(monkeypatch):
    from app.services.providers.ionos_adapter import IONOSAdapter

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"id": "meta-llama/Meta-Llama-3.1-8B-Instruct"},
            {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1"},
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
    )
    monkeypatch.setattr(adapter, "_http", mock_client)

    models = await adapter.list_models()
    assert "meta-llama/Meta-Llama-3.1-8B-Instruct" in models
    assert len(models) == 2


@pytest.mark.asyncio
async def test_list_models_caches_result(monkeypatch):
    import app.services.providers.ionos_adapter as _mod
    _mod._MODEL_CACHE.clear()  # isolate from previous test runs

    from app.services.providers.ionos_adapter import IONOSAdapter

    call_count = 0

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "model-a"}]}
    mock_resp.raise_for_status = MagicMock()

    async def counting_get(*a, **kw):
        nonlocal call_count
        call_count += 1
        return mock_resp

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
        model_cache_ttl=60,
    )
    monkeypatch.setattr(adapter, "_http", AsyncMock(get=counting_get))

    await adapter.list_models()
    await adapter.list_models()

    assert call_count == 1  # second call hit cache


# ── IONOSAdapter.chat ─────────────────────────────────────────────────────

def test_chat_returns_text_and_usage(monkeypatch):
    from app.services.providers.ionos_adapter import IONOSAdapter

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="Hello world"))]
    fake_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    mock_openai = MagicMock()
    mock_openai.chat.completions.create = MagicMock(return_value=fake_resp)

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
    )
    monkeypatch.setattr(adapter, "_openai", mock_openai)

    text, usage = adapter.chat(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        temperature=0.5,
    )
    assert text == "Hello world"
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5


# ── routing_matrix ────────────────────────────────────────────────────────

def test_routing_matrix_returns_configured_model():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "ionos-fast"
        mock_cfg.return_value.IONOS_API_KEY = "key"
        mock_cfg.return_value.ANTHROPIC_API_KEY = "key"
        mock_cfg.return_value.OPENAI_API_KEY = ""
        model = resolve_model("suggest", complexity="low")
        assert model == "ionos-fast"


def test_routing_matrix_falls_back_on_no_key():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "ionos-fast"
        mock_cfg.return_value.IONOS_API_KEY = ""          # key missing
        mock_cfg.return_value.ANTHROPIC_API_KEY = "key"
        mock_cfg.return_value.OPENAI_API_KEY = ""
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "claude-haiku-4-5"
        model = resolve_model("suggest", complexity="low")
        assert model == "claude-haiku-4-5"


def test_routing_matrix_auto_uses_ionos_when_key_set():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "auto"
        mock_cfg.return_value.IONOS_API_KEY = "some-key"
        mock_cfg.return_value.ANTHROPIC_API_KEY = ""
        mock_cfg.return_value.OPENAI_API_KEY = ""
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "ionos-fast"
        model = resolve_model("suggest", complexity="low")
        assert model == "ionos-fast"


def test_routing_matrix_auto_uses_anthropic_when_no_ionos():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "auto"
        mock_cfg.return_value.IONOS_API_KEY = ""
        mock_cfg.return_value.ANTHROPIC_API_KEY = "some-key"
        mock_cfg.return_value.OPENAI_API_KEY = ""
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "claude-haiku-4-5"
        model = resolve_model("suggest", complexity="low")
        assert model == "claude-haiku-4-5"


def test_routing_matrix_auto_high_complexity_ionos_uses_reasoning():
    """high complexity with IONOS key must route to ionos-reasoning (Mixtral 8x7B)."""
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "auto"
        mock_cfg.return_value.IONOS_API_KEY = "some-key"
        mock_cfg.return_value.ANTHROPIC_API_KEY = ""
        mock_cfg.return_value.OPENAI_API_KEY = ""
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "claude-sonnet-4-6"
        model = resolve_model("suggest", complexity="high")
        assert model == "ionos-reasoning"


def test_routing_matrix_auto_medium_complexity_ionos_uses_quality():
    """medium complexity with IONOS key must route to ionos-quality."""
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "auto"
        mock_cfg.return_value.IONOS_API_KEY = "some-key"
        mock_cfg.return_value.ANTHROPIC_API_KEY = ""
        mock_cfg.return_value.OPENAI_API_KEY = ""
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "claude-sonnet-4-6"
        model = resolve_model("suggest", complexity="medium")
        assert model == "ionos-quality"
