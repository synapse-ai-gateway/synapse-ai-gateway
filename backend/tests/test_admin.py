"""Admin-plane tests: JWT auth, api_key masking, and input validation.

The admin console authenticates with JWT (which DOES expire), so the spec's
"expired credential is rejected" case is verified here against the admin token.
"""
from __future__ import annotations

from datetime import timedelta

from conftest import TEST_API_KEY

from auth import create_access_token


# ── Login / JWT ─────────────────────────────────────────────────────────────
async def test_login_success(client, admin_user):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "TestAdminPassword_123!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["user"]["username"] == "admin"


async def test_login_wrong_password_returns_401(client, admin_user):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_expired_admin_jwt_rejected(client, admin_user):
    token, _ = create_access_token(
        data={"sub": str(admin_user.id), "role": "superadmin", "username": "admin"},
        expires_delta=timedelta(seconds=-1),
    )
    resp = await client.get("/admin/teams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_protected_endpoint_requires_token(client):
    resp = await client.get("/admin/teams")
    assert resp.status_code in (401, 403)


# ── api_key masking ───────────────────────────────────────────────────────--
async def test_team_list_masks_api_key(client, gateway, admin_headers):
    await gateway.add_team(api_key=TEST_API_KEY)
    resp = await client.get("/admin/teams", headers=admin_headers)
    assert resp.status_code == 200
    returned = resp.json()[0]["api_key"]
    assert returned != TEST_API_KEY
    assert returned.startswith("*")
    assert returned.endswith(TEST_API_KEY[-8:])


# ── Settings validation ──────────────────────────────────────────────────────
async def test_settings_rejects_unknown_key(client, admin_headers):
    resp = await client.patch(
        "/admin/settings", headers=admin_headers, json={"definitely_not_a_setting": "x"}
    )
    assert resp.status_code == 400


async def test_settings_updates_known_key(client, gateway, admin_headers):
    await gateway.set_setting("timeout_sec", "30")
    resp = await client.patch("/admin/settings", headers=admin_headers, json={"timeout_sec": "45"})
    assert resp.status_code == 200
    assert resp.json()["timeout_sec"] == "45"


# ── DLP / team input validation ───────────────────────────────────────────--
async def test_create_dlp_pattern_rejects_invalid_severity(client, admin_headers):
    resp = await client.post(
        "/admin/dlp-patterns",
        headers=admin_headers,
        json={"name": "test_pat", "pattern": r"\d+", "severity": "Bogus"},
    )
    assert resp.status_code == 400


async def test_create_dlp_pattern_accepts_valid_severity(client, admin_headers):
    resp = await client.post(
        "/admin/dlp-patterns",
        headers=admin_headers,
        json={"name": "test_pat", "pattern": r"\d{3}", "severity": "High"},
    )
    assert resp.status_code == 201
    assert resp.json()["severity"] == "High"


async def test_create_team_rejects_nonpositive_requests(client, admin_headers):
    resp = await client.post(
        "/admin/teams",
        headers=admin_headers,
        json={"team_name": "X", "model": "m", "requests": 0, "window_sec": 60},
    )
    assert resp.status_code == 422  # pydantic ge=1 validation error
