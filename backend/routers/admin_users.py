"""
Admin Users router — user management (superadmin only) + activity log.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password, require_role, validate_password_strength
from config import settings
from database import get_db
from models import User, UserActivityLog

router = APIRouter()

ROLE_HIERARCHY = {"readonly": 0, "analyst": 1, "admin": 2, "superadmin": 3}


def _mask_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "enabled": user.enabled,
        "force_password_change": user.force_password_change,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_by": user.created_by,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


async def _count_superadmins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).where(User.role == "superadmin", User.enabled == True)  # noqa: E712
    )
    return result.scalar_one()


def _generate_temp_password(length: int | None = None) -> str:
    if length is None:
        length = settings.TEMP_PASSWORD_LENGTH
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*()" for c in pwd)
        ):
            return pwd


# ── List users ──────────────────────────────────────────────────────────────
@router.get("/users")
async def list_users(
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [_mask_user(u) for u in users]


# ── Create user ──────────────────────────────────────────────────────────────
class CreateUserBody(BaseModel):
    username: str
    full_name: str
    email: str
    role: str
    temp_password: str


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserBody,
    request: Request,
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    ok, msg = validate_password_strength(body.temp_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # Check username/email uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Username already exists.")
    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=409, detail="Email already in use.")

    now = datetime.utcnow()
    new_user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        hashed_password=hash_password(body.temp_password),
        role=body.role,
        enabled=True,
        force_password_change=True,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(new_user)
    await db.flush()

    db.add(
        UserActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action="user.create",
            target_type="users",
            target_id=body.username,
            changes={"after": {"username": body.username, "role": body.role}},
            ip_address=request.client.host if request.client else None,
            timestamp=now,
        )
    )
    await db.commit()
    await db.refresh(new_user)
    return _mask_user(new_user)


# ── Update user ──────────────────────────────────────────────────────────────
class UpdateUserBody(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    enabled: Optional[bool] = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserBody,
    request: Request,
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Guard: cannot demote or disable the last superadmin
    if target.role == "superadmin":
        if (body.role and body.role != "superadmin") or (body.enabled is False):
            count = await _count_superadmins(db)
            if count <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot demote or disable the last superadmin account.",
                )

    if body.role and body.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    changes: dict = {}
    now = datetime.utcnow()

    if body.full_name is not None:
        changes["full_name"] = {"before": target.full_name, "after": body.full_name}
        target.full_name = body.full_name
    if body.email is not None:
        changes["email"] = {"before": target.email, "after": body.email}
        target.email = body.email
    if body.role is not None:
        changes["role"] = {"before": target.role, "after": body.role}
        target.role = body.role
    if body.enabled is not None:
        changes["enabled"] = {"before": target.enabled, "after": body.enabled}
        target.enabled = body.enabled
    target.updated_at = now

    db.add(
        UserActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action="user.update",
            target_type="users",
            target_id=target.username,
            changes=changes,
            ip_address=request.client.host if request.client else None,
            timestamp=now,
        )
    )
    await db.commit()
    await db.refresh(target)
    return _mask_user(target)


# ── Reset password ────────────────────────────────────────────────────────────
@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    request: Request,
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    from models import UserPasswordHistory  # noqa: PLC0415

    temp_pwd = _generate_temp_password()
    now = datetime.utcnow()

    # Save current password to history before overwriting (§3.1)
    db.add(UserPasswordHistory(
        user_id=target.id,
        hashed_password=target.hashed_password,
        changed_at=now,
    ))

    target.hashed_password = hash_password(temp_pwd)
    target.force_password_change = True
    target.password_changed_at = now
    target.updated_at = now

    db.add(
        UserActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action="user.reset_password",
            target_type="users",
            target_id=target.username,
            changes={"note": "password reset by superadmin"},
            ip_address=request.client.host if request.client else None,
            timestamp=now,
        )
    )
    await db.commit()
    # Return temp password ONCE — caller must display to admin
    return {"temp_password": temp_pwd, "force_password_change": True}


# ── Activity log ─────────────────────────────────────────────────────────────
@router.get("/activity-log")
async def get_activity_log(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(UserActivityLog).order_by(UserActivityLog.timestamp.desc())

    if from_date:
        query = query.where(UserActivityLog.timestamp >= datetime.fromisoformat(from_date))
    if to_date:
        query = query.where(UserActivityLog.timestamp <= datetime.fromisoformat(to_date))
    if username:
        query = query.where(UserActivityLog.username.ilike(f"%{username}%"))
    if action:
        query = query.where(UserActivityLog.action.ilike(f"%{action}%"))
    if target_type:
        query = query.where(UserActivityLog.target_type == target_type)

    count_q = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    rows = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "username": r.username,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "changes": r.changes,
                "ip_address": r.ip_address,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }
