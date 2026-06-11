"""Login lockout, token refresh/logout, and password-change flows."""
from __future__ import annotations

from datetime import datetime

from auth import create_access_token, hash_password


async def _make_user(db, *, username: str, password: str, force_change: bool = False):
    from models import User

    now = datetime.utcnow()
    user = User(
        username=username,
        email=f"{username}@yourorg.com",
        full_name=username.title(),
        hashed_password=hash_password(password),
        role="admin",
        enabled=True,
        force_password_change=force_change,
        password_changed_at=None if force_change else now,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token, jti = create_access_token(
        data={"sub": str(user.id), "role": user.role, "username": user.username}
    )
    user.active_session_jti = jti
    await db.commit()
    return user, {"Authorization": f"Bearer {token}"}


async def test_account_lockout_after_max_failed_logins(client, gateway, admin_user):
    await gateway.set_setting("max_failed_logins", "2")
    bad = {"username": "admin", "password": "nope"}

    r1 = await client.post("/auth/login", json=bad)
    r2 = await client.post("/auth/login", json=bad)
    assert r1.status_code == 401
    assert r2.status_code == 423  # locked on reaching the threshold


async def test_refresh_token(client, admin_headers):
    resp = await client.post("/auth/refresh", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["token"]


async def test_logout(client, admin_headers):
    resp = await client.post("/auth/logout", headers=admin_headers)
    assert resp.status_code == 200


async def test_change_password_success(client, db):
    _, headers = await _make_user(db, username="changer", password="OldPass_12345!", force_change=True)
    resp = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass_12345!", "new_password": "NewPass_67890!"},
    )
    assert resp.status_code == 200


async def test_change_password_wrong_current_returns_401(client, db):
    _, headers = await _make_user(db, username="changer2", password="OldPass_12345!", force_change=True)
    resp = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "WRONG", "new_password": "NewPass_67890!"},
    )
    assert resp.status_code == 401


async def test_change_password_weak_rejected(client, db):
    _, headers = await _make_user(db, username="changer3", password="OldPass_12345!", force_change=True)
    resp = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "OldPass_12345!", "new_password": "weak"},
    )
    assert resp.status_code == 400
