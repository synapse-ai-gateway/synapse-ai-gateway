"""Admin CRUD coverage: teams, users, DLP patterns, settings, stats, models."""
from __future__ import annotations


# ── Teams lifecycle ───────────────────────────────────────────────────────--
async def test_team_crud_lifecycle(client, admin_headers):
    create = await client.post(
        "/admin/teams",
        headers=admin_headers,
        json={"team_name": "Sales", "model": "m1", "requests": 5, "window_sec": 60},
    )
    assert create.status_code == 201
    team = create.json()
    team_id = team["id"]
    assert team["api_key"]  # full key returned once on creation

    listed = await client.get("/admin/teams", headers=admin_headers)
    assert listed.status_code == 200
    assert any(t["id"] == team_id for t in listed.json())

    reveal = await client.get(f"/admin/teams/{team_id}/api-key", headers=admin_headers)
    assert reveal.status_code == 200
    assert reveal.json()["api_key"] == team["api_key"]

    updated = await client.patch(
        f"/admin/teams/{team_id}", headers=admin_headers, json={"requests": 50}
    )
    assert updated.status_code == 200
    assert updated.json()["requests"] == 50

    deleted = await client.delete(f"/admin/teams/{team_id}", headers=admin_headers)
    assert deleted.status_code == 200


async def test_update_missing_team_returns_404(client, admin_headers):
    resp = await client.patch("/admin/teams/9999", headers=admin_headers, json={"requests": 1})
    assert resp.status_code == 404


# ── Users lifecycle ───────────────────────────────────────────────────────--
async def test_user_crud_and_activity_log(client, admin_headers):
    create = await client.post(
        "/admin/users",
        headers=admin_headers,
        json={
            "username": "analyst1",
            "full_name": "Ana Lyst",
            "email": "analyst1@yourorg.com",
            "role": "analyst",
            "temp_password": "ValidPass_12345!",
        },
    )
    assert create.status_code == 201
    user_id = create.json()["id"]

    listed = await client.get("/admin/users", headers=admin_headers)
    assert listed.status_code == 200
    assert any(u["username"] == "analyst1" for u in listed.json())

    updated = await client.patch(
        f"/admin/users/{user_id}", headers=admin_headers, json={"full_name": "Updated Name"}
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Name"

    reset = await client.post(f"/admin/users/{user_id}/reset-password", headers=admin_headers)
    assert reset.status_code == 200
    assert reset.json()["temp_password"]

    activity = await client.get("/admin/activity-log", headers=admin_headers)
    assert activity.status_code == 200
    actions = {item["action"] for item in activity.json()["items"]}
    assert "user.create" in actions


async def test_create_user_duplicate_username_conflict(client, admin_headers):
    body = {
        "username": "dup",
        "full_name": "Dup User",
        "email": "dup@yourorg.com",
        "role": "analyst",
        "temp_password": "ValidPass_12345!",
    }
    first = await client.post("/admin/users", headers=admin_headers, json=body)
    assert first.status_code == 201
    second = await client.post(
        "/admin/users", headers=admin_headers, json={**body, "email": "dup2@yourorg.com"}
    )
    assert second.status_code == 409


# ── DLP patterns lifecycle ────────────────────────────────────────────────--
async def test_dlp_pattern_crud(client, admin_headers):
    create = await client.post(
        "/admin/dlp-patterns",
        headers=admin_headers,
        json={"name": "zipcode", "pattern": r"\d{5}", "severity": "Low"},
    )
    assert create.status_code == 201

    listed = await client.get("/admin/dlp-patterns", headers=admin_headers)
    assert any(p["name"] == "zipcode" for p in listed.json())

    updated = await client.patch(
        "/admin/dlp-patterns/zipcode", headers=admin_headers, json={"enabled": False}
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    deleted = await client.delete("/admin/dlp-patterns/zipcode", headers=admin_headers)
    assert deleted.status_code == 200


async def test_create_dlp_pattern_invalid_regex_returns_400(client, admin_headers):
    resp = await client.post(
        "/admin/dlp-patterns",
        headers=admin_headers,
        json={"name": "bad", "pattern": "([unclosed", "severity": "Low"},
    )
    assert resp.status_code == 400


# ── Settings / stats ──────────────────────────────────────────────────────--
async def test_get_settings_excludes_sensitive(client, gateway, admin_headers):
    await gateway.set_setting("timeout_sec", "30")
    resp = await client.get("/admin/settings", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "timeout_sec" in body
    assert "JWT_SECRET" not in body
    assert "ADMIN_PASSWORD" not in body


async def test_stats_summary_and_per_team(client, gateway, admin_headers):
    await gateway.add_team()
    summary = await client.get("/admin/stats/summary", headers=admin_headers)
    assert summary.status_code == 200
    for key in ("total_requests_today", "dlp_blocks_today", "rate_limit_hits_today", "active_teams"):
        assert key in summary.json()

    per_team = await client.get("/admin/stats/per-team", headers=admin_headers)
    assert per_team.status_code == 200
    assert per_team.json()["window_minutes"] == 60


# ── Audit / incident listing + export ─────────────────────────────────────--
async def test_audit_list_and_export(client, gateway, mock_llm, flush_background, admin_headers):
    from conftest import auth_header

    await gateway.add_team()
    await client.post(
        "/v1/chat/completions",
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    await flush_background()

    listed = await client.get("/admin/audit", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    # api_key must be masked in the audit listing.
    assert listed.json()["items"][0]["api_key"].startswith("*")

    export = await client.get("/admin/audit/export", headers=admin_headers)
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]


async def test_incidents_list_and_export(client, gateway, mock_llm, flush_background, admin_headers):
    from conftest import auth_header

    await gateway.add_team()
    await gateway.add_default_dlp_patterns()
    await client.post(
        "/v1/chat/completions",
        headers=auth_header(),
        json={"messages": [{"role": "user", "content": "id 42101-1234567-1"}]},
    )
    await flush_background()

    listed = await client.get("/admin/incidents", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert listed.json()["items"][0]["api_key"].startswith("*")

    export = await client.get("/admin/incidents/export", headers=admin_headers)
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]


# ── Models proxy ──────────────────────────────────────────────────────────--
async def test_models_endpoint_handles_unreachable_backend(client, gateway, admin_headers):
    # Point at a closed port so the connect fails deterministically -> 502.
    await gateway.set_setting("vllm_url", "http://127.0.0.1:1/v1")
    resp = await client.get("/admin/models", headers=admin_headers)
    assert resp.status_code == 502


# ── Authorisation: role enforcement ───────────────────────────────────────--
async def test_analyst_cannot_create_team(client, db, admin_headers):
    """An analyst (role below 'admin') must be rejected from team creation."""
    from datetime import datetime

    from auth import create_access_token, hash_password
    from models import User

    now = datetime.utcnow()
    analyst = User(
        username="ro_analyst",
        email="ro@yourorg.com",
        full_name="RO",
        hashed_password=hash_password("ValidPass_12345!"),
        role="analyst",
        enabled=True,
        force_password_change=False,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(analyst)
    await db.commit()
    await db.refresh(analyst)
    token, jti = create_access_token(
        data={"sub": str(analyst.id), "role": "analyst", "username": "ro_analyst"}
    )
    analyst.active_session_jti = jti
    await db.commit()

    resp = await client.post(
        "/admin/teams",
        headers={"Authorization": f"Bearer {token}"},
        json={"team_name": "X", "model": "m", "requests": 1, "window_sec": 60},
    )
    assert resp.status_code == 403
