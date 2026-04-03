"""Tests for the retry / backoff module."""
import asyncio
import pytest

from app.core.retry import (
    RetryConfig,
    retry_on_rate_limit,
    parse_retry_after,
    RateLimitExhausted,
)


def test_parse_retry_after_numeric():
    assert parse_retry_after({"retry-after": "5"}) == 5.0


def test_parse_retry_after_missing():
    assert parse_retry_after({}) is None


def test_parse_retry_after_non_numeric_ignored():
    assert parse_retry_after({"retry-after": "Wed, 21 Oct 2025 07:28:00 GMT"}) is None


def test_parse_retry_after_float():
    assert parse_retry_after({"retry-after": "1.5"}) == 1.5


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_on_rate_limit(fn, RetryConfig(max_attempts=3, base_delay=0.01))
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_recovers_after_one_429():
    calls = []

    class FakeRateLimit(Exception):
        status_code = 429
        response_headers: dict = {}

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise FakeRateLimit("rate limited")
        return "recovered"

    result = await retry_on_rate_limit(
        fn,
        RetryConfig(max_attempts=3, base_delay=0.01),
        is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
    )
    assert result == "recovered"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_raises():
    class FakeRateLimit(Exception):
        status_code = 429
        response_headers: dict = {}

    async def fn():
        raise FakeRateLimit("always limited")

    with pytest.raises(RateLimitExhausted):
        await retry_on_rate_limit(
            fn,
            RetryConfig(max_attempts=2, base_delay=0.01),
            is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
        )


@pytest.mark.asyncio
async def test_non_rate_limit_exception_propagates():
    async def fn():
        raise ValueError("unexpected")

    with pytest.raises(ValueError):
        await retry_on_rate_limit(
            fn,
            RetryConfig(max_attempts=3, base_delay=0.01),
        )


@pytest.mark.asyncio
async def test_retry_after_header_is_respected(monkeypatch):
    waited = []

    async def fake_sleep(secs):
        waited.append(secs)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    class FakeRateLimit(Exception):
        status_code = 429
        response_headers = {"retry-after": "3"}

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise FakeRateLimit()
        return "ok"

    await retry_on_rate_limit(
        fn,
        RetryConfig(max_attempts=3, base_delay=0.01, max_delay=10.0),
        is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
        get_headers=lambda e: e.response_headers,
    )

    assert waited[0] == 3.0
