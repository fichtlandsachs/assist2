import pytest
from unittest.mock import patch, MagicMock
import httpx


def test_chat_returns_text_and_usage():
    from app.llm.client import LiteLLMClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"score": 7.5}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "model": "eval-quality",
    }
    mock_response.raise_for_status = MagicMock()

    client = LiteLLMClient(base_url="http://fake:4000", api_key="test")
    with patch("httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post = MagicMock(return_value=mock_response)

        text, usage = client.chat(
            model="eval-quality",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )

    assert text == '{"score": 7.5}'
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50
    assert usage["model"] == "eval-quality"


def test_chat_raises_on_timeout():
    from app.llm.client import LiteLLMClient, LLMCallError

    client = LiteLLMClient(base_url="http://fake:4000", api_key="test")
    with patch("httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post = MagicMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(LLMCallError, match="timeout"):
            client.chat(model="eval-fast", messages=[], max_tokens=10)


def test_chat_raises_on_http_error():
    from app.llm.client import LiteLLMClient, LLMCallError

    client = LiteLLMClient(base_url="http://fake:4000", api_key="test")
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service Unavailable"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response)
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.post = MagicMock(return_value=mock_response)

        with pytest.raises(LLMCallError, match="503"):
            client.chat(model="eval-fast", messages=[], max_tokens=10)
