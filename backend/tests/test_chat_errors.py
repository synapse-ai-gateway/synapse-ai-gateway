"""Chat pipeline error branches and streaming."""
from __future__ import annotations

import httpx
from conftest import FakeResponse, FakeStreamResponse, auth_header

ENDPOINT = "/v1/chat/completions"
BODY = {"messages": [{"role": "user", "content": "hello"}]}


async def test_upstream_non_2xx_returns_502(client, gateway, mock_llm, flush_background):
    await gateway.add_team()
    mock_llm.response = FakeResponse(status_code=500, payload={"error": "backend boom"})
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 502
    await flush_background()


async def test_upstream_timeout_returns_504(client, gateway, mock_llm, flush_background):
    await gateway.add_team()
    mock_llm.exc = httpx.TimeoutException("timed out")
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 504
    await flush_background()


async def test_upstream_connect_error_returns_502(client, gateway, mock_llm, flush_background):
    await gateway.add_team()
    mock_llm.exc = httpx.ConnectError("refused")
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 502
    await flush_background()


async def test_invalid_json_from_backend_returns_502(client, gateway, mock_llm, flush_background):
    await gateway.add_team()

    class BadJSON(FakeResponse):
        def json(self):
            raise ValueError("not json")

    mock_llm.response = BadJSON(status_code=200)
    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 502
    await flush_background()


async def test_response_dlp_block_returns_502(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await gateway.add_default_dlp_patterns()
    # Backend echoes a US SSN in its response.
    leaked = {
        "id": "x",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "here: 123-45-6789"}}],
        "usage": {"total_tokens": 9},
    }
    mock_llm.response = FakeResponse(status_code=200, payload=leaked)

    resp = await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": "clean"}]}
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["error"] == "Response blocked by DLP policy"

    await flush_background()
    from sqlalchemy import select

    from models import DLPIncident

    rows = (await db.execute(select(DLPIncident))).scalars().all()
    assert any(r.source == "model_response" for r in rows)


async def test_streaming_success(client, gateway, mock_llm, flush_background):
    await gateway.add_team()
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert b"[DONE]" in resp.content
    await flush_background()


async def test_streaming_upstream_error_emits_sse_error(client, gateway, mock_llm, flush_background):
    await gateway.add_team()
    mock_llm.stream_response = FakeStreamResponse(status_code=500, chunks=[b'{"error":"upstream"}'])
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert resp.status_code == 200  # StreamingResponse status is 200; error is in the SSE body
    assert b"error" in resp.content
    await flush_background()
