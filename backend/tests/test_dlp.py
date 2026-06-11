"""DLP scanning tests — block, redact, alert modes plus incident persistence."""
from __future__ import annotations

import pytest
from conftest import auth_header
from sqlalchemy import select

ENDPOINT = "/v1/chat/completions"


@pytest.fixture
async def configured(gateway):
    await gateway.add_team()
    await gateway.add_default_dlp_patterns()
    return gateway


async def test_clean_prompt_passes_through(client, configured, mock_llm):
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "what is the weather in london"}]},
    )
    assert resp.status_code == 200
    assert len(mock_llm.calls) == 1
    # Prompt forwarded unchanged to the backend.
    assert mock_llm.calls[0]["json"]["messages"][-1]["content"] == "what is the weather in london"


@pytest.mark.parametrize(
    "content,expected_pattern",
    [
        ("my ssn is 123-45-6789 please help", "us_ssn"),               # US Social Security Number
        ("here is my card 4111111111111111 ok", "credit_card"),        # card PAN
        ("config has key AKIAIOSFODNN7EXAMPLE oops", "aws_access_key"),  # leaked AWS access key id
    ],
)
async def test_prompt_with_pii_is_blocked(client, configured, mock_llm, content, expected_pattern):
    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": content}]},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "Request blocked by DLP policy"
    assert detail["incident_id"]
    matched = {f["pattern"] for f in detail["findings"]}
    assert expected_pattern in matched
    # Blocked before the backend is ever contacted.
    assert len(mock_llm.calls) == 0


async def test_block_persists_dlp_incident(client, configured, mock_llm, flush_background, db):
    from models import DLPIncident

    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "ssn 123-45-6789"}]},
    )
    assert resp.status_code == 400
    await flush_background()

    rows = (await db.execute(select(DLPIncident))).scalars().all()
    assert len(rows) == 1
    incident = rows[0]
    assert incident.source == "user_input"
    assert incident.action == "block"
    assert incident.max_severity == "Critical"
    assert "us_ssn" in incident.patterns
    assert not hasattr(incident, "message")
    assert incident.message_len > 0


async def test_redact_mode_sanitises_and_routes(client, gateway, mock_llm, flush_background, db):
    from models import DLPIncident

    await gateway.add_team()
    # A "phone" pattern with REDACT action.
    await gateway.add_dlp_pattern(
        name="phone_redact", pattern=r"\b\d{3}-\d{4}\b", severity="Medium", action="redact"
    )

    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "call me on 555-1234 please"}]},
    )
    assert resp.status_code == 200

    forwarded = mock_llm.calls[0]["json"]["messages"][-1]["content"]
    assert "555-1234" not in forwarded
    assert "[REDACTED:phone_redact]" in forwarded

    await flush_background()
    rows = (await db.execute(select(DLPIncident))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "redact"


async def test_alert_mode_routes_and_logs(client, gateway, mock_llm, flush_background, db):
    from models import DLPIncident

    await gateway.add_team()
    await gateway.add_dlp_pattern(
        name="phone_alert", pattern=r"\b\d{3}-\d{4}\b", severity="Low", action="alert"
    )

    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "call 555-1234 today"}]},
    )
    assert resp.status_code == 200

    forwarded = mock_llm.calls[0]["json"]["messages"][-1]["content"]
    # Alert mode does NOT modify the prompt.
    assert "555-1234" in forwarded
    assert "[REDACTED" not in forwarded

    await flush_background()
    rows = (await db.execute(select(DLPIncident))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "alert"


async def test_block_wins_when_combined_with_redact(client, gateway, mock_llm, flush_background):
    """If any matching pattern is BLOCK, the request is rejected regardless of REDACT patterns."""
    await gateway.add_team()
    await gateway.add_dlp_pattern(
        name="redact_phone", pattern=r"\b\d{3}-\d{4}\b", severity="Medium", action="redact"
    )
    await gateway.add_dlp_pattern(
        name="block_cnic", pattern=r"\b\d{5}-\d{7}-\d{1}\b", severity="Critical", action="block"
    )

    resp = await client.post(
        ENDPOINT,
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "call 555-1234 id 42101-1234567-1"}]},
    )
    assert resp.status_code == 400
    assert len(mock_llm.calls) == 0
