"""Hybrid routing — sensitive teams go on-prem, non-sensitive may go to cloud."""
from __future__ import annotations

from conftest import auth_header

ENDPOINT = "/v1/chat/completions"
BODY = {"messages": [{"role": "user", "content": "hello"}]}


async def test_sensitive_classification_routes_to_on_premises(client, gateway, mock_llm):
    await gateway.set_setting("vllm_url", "http://on-prem.example/v1")
    await gateway.set_setting("cloud_vllm_url", "http://cloud.example/v1")
    await gateway.add_team(data_classification="sensitive")

    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 200
    assert mock_llm.calls[0]["url"].startswith("http://on-prem.example/v1")


async def test_non_sensitive_classification_routes_to_cloud(client, gateway, mock_llm):
    await gateway.set_setting("vllm_url", "http://on-prem.example/v1")
    await gateway.set_setting("cloud_vllm_url", "http://cloud.example/v1")
    await gateway.add_team(data_classification="non_sensitive")

    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 200
    assert mock_llm.calls[0]["url"].startswith("http://cloud.example/v1")


async def test_non_sensitive_falls_back_to_on_premises_when_no_cloud_configured(
    client, gateway, mock_llm
):
    await gateway.set_setting("vllm_url", "http://on-prem.example/v1")
    # cloud_vllm_url is intentionally NOT set.
    await gateway.add_team(data_classification="non_sensitive")

    resp = await client.post(ENDPOINT, headers=auth_header(), json=BODY)
    assert resp.status_code == 200
    # Safe fallback: stay on-prem rather than fail.
    assert mock_llm.calls[0]["url"].startswith("http://on-prem.example/v1")
