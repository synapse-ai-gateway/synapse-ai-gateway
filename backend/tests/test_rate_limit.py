"""Rate-limiting tests — per-window request limit and per-day token budget."""
from __future__ import annotations

from conftest import auth_header

ENDPOINT = "/v1/chat/completions"
BODY = {"messages": [{"role": "user", "content": "a clean prompt"}]}


async def test_request_within_limit_accepted(client, gateway, mock_llm):
    await gateway.add_team(requests=5, window_sec=60)
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 200


async def test_request_exceeding_per_window_limit_returns_429(client, gateway, mock_llm):
    await gateway.add_team(requests=2, window_sec=60)

    r1 = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    r2 = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    r3 = await client.post(ENDPOINT, headers=auth_header(), json=BODY)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


async def test_429_response_contains_rate_limit_metadata(client, gateway, mock_llm):
    await gateway.add_team(requests=1, window_sec=60)
    await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["error"] == "Rate limit exceeded"
    assert detail["limit"] == 1
    assert detail["window_sec"] == 60
    assert detail["retry_after"] >= 1


async def test_429_includes_rate_limit_headers(client, gateway, mock_llm):
    await gateway.add_team(requests=1, window_sec=60)
    await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)

    assert resp.status_code == 429
    assert resp.headers["Retry-After"]
    assert resp.headers["X-RateLimit-Limit"] == "1"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    assert int(resp.headers["X-RateLimit-Reset"]) > 0


async def test_daily_token_budget_blocks_after_exhaustion(client, gateway, mock_llm):
    # Tiny budget — the first response (15 tokens from the mock) exceeds it.
    await gateway.add_team(tokens_per_day=10)
    first = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert first.status_code == 200  # the request that crosses the line still runs

    blocked = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert detail["error"] == "Daily token budget exhausted"
    assert detail["tokens_per_day"] == 10
    assert detail["tokens_used_today"] >= 10
    # Token-specific headers too.
    assert blocked.headers["X-RateLimit-Tokens-Limit"] == "10"
    assert blocked.headers["X-RateLimit-Tokens-Remaining"] == "0"
    assert int(blocked.headers["Retry-After"]) > 0


async def test_token_budget_unlimited_by_default(client, gateway, mock_llm):
    await gateway.add_team()  # tokens_per_day=None
    for _ in range(5):
        resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
        assert resp.status_code == 200


async def test_limits_are_per_key_isolated(client, gateway, mock_llm):
    await gateway.add_team(api_key="key-a", requests=1, window_sec=60)
    await gateway.add_team(api_key="key-b", requests=1, window_sec=60)

    # Exhaust key-a; key-b must still be accepted.
    await client.post(ENDPOINT, headers=auth_header("key-a"), json=BODY)
    blocked = await client.post(ENDPOINT, headers=auth_header("key-a"), json=BODY)
    other = await client.post(ENDPOINT, headers=auth_header("key-b"), json=BODY)

    assert blocked.status_code == 429
    assert other.status_code == 200
