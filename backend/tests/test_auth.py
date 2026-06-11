"""Authentication and authorisation tests for POST /v1/chat/completions."""
from __future__ import annotations

from datetime import datetime, timedelta

from conftest import auth_header

ENDPOINT = "/v1/chat/completions"


async def test_valid_api_key_accepted(client, gateway, mock_llm):
    await gateway.add_team()
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hello world"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "Hello, I am a test assistant."
    assert len(mock_llm.calls) == 1


async def test_invalid_api_key_returns_403(client, gateway, mock_llm):
    await gateway.add_team()
    resp = await client.post(
        ENDPOINT,
        headers=auth_header("totally-unknown-key"),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 403
    assert len(mock_llm.calls) == 0


async def test_missing_bearer_header_returns_401(client, gateway, mock_llm):
    await gateway.add_team()
    resp = await client.post(
        ENDPOINT,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 401


async def test_disabled_api_key_returns_403(client, gateway, mock_llm):
    await gateway.add_team(enabled=False)
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 403
    assert len(mock_llm.calls) == 0


async def test_expired_api_key_returns_403(client, gateway, mock_llm):
    await gateway.add_team(expires_at=datetime.utcnow() - timedelta(minutes=1))
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"].lower()
    assert len(mock_llm.calls) == 0


async def test_unexpired_api_key_works(client, gateway, mock_llm):
    await gateway.add_team(expires_at=datetime.utcnow() + timedelta(days=30))
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 200


async def test_model_not_on_allowlist_returns_403(client, gateway, mock_llm):
    await gateway.add_team(model="test-model")
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={
            "model": "some-other-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 403
    assert len(mock_llm.calls) == 0


async def test_assigned_model_used_when_caller_sends_matching_model(client, gateway, mock_llm):
    await gateway.add_team(model="test-model")
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    # The gateway forwards its assigned model, not whatever the caller passed.
    assert mock_llm.calls[0]["json"]["model"] == "test-model"
