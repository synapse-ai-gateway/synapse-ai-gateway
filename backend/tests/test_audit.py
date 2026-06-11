"""Audit-logging tests.

NOTE: only the request prompt is hashed and stored (prompt_hash). The model
response is scanned for DLP but is NOT persisted at all — there is no
response_hash column. The "response stored as hash" spec item is therefore
covered as "response is never stored in any form" (see
test_response_is_not_persisted).
"""
from __future__ import annotations

import hashlib

from conftest import auth_header
from sqlalchemy import select

ENDPOINT = "/v1/chat/completions"


async def _audit_rows(db):
    from models import AuditLog

    return (await db.execute(select(AuditLog))).scalars().all()


async def test_successful_request_is_audited(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    resp = await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 200
    await flush_background()

    rows = await _audit_rows(db)
    assert len(rows) == 1
    assert rows[0].status == "success"


async def test_invalid_key_is_audited(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await client.post(
        ENDPOINT, headers=auth_header("bad-key"), json={"messages": [{"role": "user", "content": "hi"}]}
    )
    await flush_background()

    rows = await _audit_rows(db)
    assert len(rows) == 1
    assert rows[0].status == "blocked_auth"


async def test_rate_limited_request_is_audited(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team(requests=1, window_sec=60)
    body = {"messages": [{"role": "user", "content": "hi"}]}
    await client.post(ENDPOINT, headers=auth_header(), json=body)
    await client.post(ENDPOINT, headers=auth_header(), json=body)
    await flush_background()

    statuses = sorted(r.status for r in await _audit_rows(db))
    assert statuses == ["blocked_rate_limit", "success"]


async def test_dlp_blocked_request_is_audited(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await gateway.add_default_dlp_patterns()
    await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "id 42101-1234567-1"}]},
    )
    await flush_background()

    rows = await _audit_rows(db)
    assert len(rows) == 1
    assert rows[0].status == "blocked_dlp"
    assert rows[0].dlp_flagged is True
    assert rows[0].incident_id


async def test_audit_record_contains_required_fields(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": "hi"}]}
    )
    await flush_background()

    row = (await _audit_rows(db))[0]
    for field in ("api_key", "team_name", "model", "status", "prompt_hash", "timestamp"):
        assert getattr(row, field) not in (None, ""), f"{field} missing"
    # Timing + outcome metadata captured on the success path.
    for field in ("auth_ms", "dlp_ms", "inject_ms", "vllm_ms", "latency_ms", "response_status"):
        assert getattr(row, field) is not None, f"{field} missing"
    assert row.response_status == 200
    assert row.tokens_used == 15  # from the mocked usage block


async def test_prompt_stored_as_hash_not_plaintext(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    prompt = "this is my secret prompt text"
    await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": prompt}]}
    )
    await flush_background()

    row = (await _audit_rows(db))[0]
    expected = hashlib.sha256(prompt.encode()).hexdigest()
    assert row.prompt_hash == expected
    assert row.prompt_hash != prompt
    # The plaintext prompt must not appear in ANY column of the audit record.
    serialised = " ".join(str(v) for v in vars(row).values() if not str(v).startswith("<"))
    assert prompt not in serialised


async def test_response_is_not_persisted(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": "hi"}]}
    )
    await flush_background()

    row = (await _audit_rows(db))[0]
    response_text = "Hello, I am a test assistant."  # the mocked completion content
    serialised = " ".join(str(v) for v in vars(row).values() if not str(v).startswith("<"))
    assert response_text not in serialised


async def test_response_stored_as_hash(client, gateway, mock_llm, flush_background, db):
    await gateway.add_team()
    await client.post(
        ENDPOINT, headers=auth_header(), json={"messages": [{"role": "user", "content": "hi"}]}
    )
    await flush_background()

    row = (await _audit_rows(db))[0]
    expected = hashlib.sha256(b"Hello, I am a test assistant.").hexdigest()
    assert row.response_hash == expected
    assert row.response_hash != "Hello, I am a test assistant."
