"""
Authentication router.

POST /auth/login          — issue JWT
POST /auth/change-password — change own password (requires JWT)
POST /auth/logout          — log logout event (requires JWT)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_password_strength,
    verify_password,
)
from config import settings
from database import get_db
from state import gateway_settings


# ---------------------------------------------------------------------------
# Helpers — read configurable security settings
# ---------------------------------------------------------------------------
def _get_int_setting(key: str, default: int) -> int:
    try:
        return int(gateway_settings.get(key, default))
    except (ValueError, TypeError):
        return default

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    enabled: bool
    force_password_change: bool
    last_login: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    force_password_change: bool
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


async def _log_activity(
    db: AsyncSession,
    user_id: int,
    username: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    ip_address: str | None = None,
    changes: dict | None = None,
) -> None:
    from models import UserActivityLog  # noqa: PLC0415

    log = UserActivityLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        changes=changes,
        ip_address=ip_address,
        timestamp=datetime.utcnow(),
    )
    db.add(log)
    await db.commit()


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    from models import User  # noqa: PLC0415

    max_failed        = _get_int_setting("max_failed_logins", settings.MAX_FAILED_LOGINS)
    lockout_minutes   = _get_int_setting("lockout_minutes", settings.LOCKOUT_MINUTES)
    expire_hours      = _get_int_setting("access_token_expire_hours", settings.ACCESS_TOKEN_EXPIRE_HOURS)
    inactivity_days   = _get_int_setting("inactivity_disable_days", settings.INACTIVITY_DISABLE_DAYS)
    max_pwd_age_days  = _get_int_setting("max_password_age_days", settings.MAX_PASSWORD_AGE_DAYS)

    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user: User | None = result.scalars().first()

    # ---- Account lock check (before password verify to prevent timing oracle)
    now = datetime.utcnow()

    if user and user.locked_until and user.locked_until > now:
        retry_after = int((user.locked_until - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "Account locked",
                "retry_after": retry_after,
            },
        )

    # ---- Credential check
    if user is None or not verify_password(body.password, user.hashed_password):
        if user is not None:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= max_failed:
                user.locked_until = now + timedelta(minutes=lockout_minutes)
                user.failed_login_attempts = 0
            await db.commit()

            if user.locked_until and user.locked_until > now:
                retry_after = int((user.locked_until - now).total_seconds())
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "error": "Account locked",
                        "retry_after": retry_after,
                    },
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    # ---- §3.2 Inactive account auto-disable (90 days)
    if user.last_login and inactivity_days > 0:
        days_inactive = (now - user.last_login).days
        if days_inactive >= inactivity_days:
            user.enabled = False
            await db.commit()
            await _log_activity(
                db, user_id=user.id, username=user.username,
                action="auto_disabled_inactive",
                target_type="user", target_id=str(user.id),
                changes={"reason": f"No login for {days_inactive} days"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Account disabled due to {days_inactive} days of inactivity. Contact an administrator.",
            )

    # ---- Successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now

    # ---- §6.4 Single session — rotate jti, invalidate previous session
    from state import gateway_settings as gs  # noqa: PLC0415
    single_session = gs.get(
        "single_session_per_user", str(settings.SINGLE_SESSION_PER_USER).lower()
    ) == "true"

    # ---- §3.1 Password age expiry check
    force_change = user.force_password_change
    if not force_change and max_pwd_age_days > 0 and user.password_changed_at:
        age_days = (now - user.password_changed_at).days
        if age_days >= max_pwd_age_days:
            user.force_password_change = True
            force_change = True

    await db.commit()

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        user_id=user.id,
        username=user.username,
        action="login",
        target_type="session",
        target_id="",
        ip_address=client_ip,
    )

    token, jti = create_access_token(
        data={"sub": str(user.id), "role": user.role, "username": user.username},
        expires_delta=timedelta(hours=expire_hours),
    )

    # Store jti for single-session enforcement
    if single_session:
        user.active_session_jti = jti
        await db.commit()

    return LoginResponse(
        token=token,
        force_password_change=force_change,
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            enabled=user.enabled,
            force_password_change=user.force_password_change,
            last_login=user.last_login,
            created_by=user.created_by,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------
@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import User  # noqa: PLC0415

    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    valid, reason = validate_password_strength(body.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    result = await db.execute(select(User).where(User.id == current_user.id))
    user: User = result.scalars().first()

    now = datetime.utcnow()

    # §3.1 Minimum password age — prevent cycling through history too fast
    min_age_days = _get_int_setting("min_password_age_days", settings.MIN_PASSWORD_AGE_DAYS)
    if min_age_days > 0 and user.password_changed_at and not user.force_password_change:
        age_hours = (now - user.password_changed_at).total_seconds() / 3600
        if age_hours < min_age_days * 24:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password can only be changed once every {min_age_days} day(s).",
            )

    # §3.1 Password history — reject reuse of last N passwords
    from models import UserPasswordHistory  # noqa: PLC0415
    history_count = _get_int_setting("password_history_count", settings.PASSWORD_HISTORY_COUNT)
    if history_count > 0:
        hist_result = await db.execute(
            select(UserPasswordHistory)
            .where(UserPasswordHistory.user_id == user.id)
            .order_by(UserPasswordHistory.changed_at.desc())
            .limit(history_count)
        )
        history = hist_result.scalars().all()
        for entry in history:
            if verify_password(body.new_password, entry.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Password was used recently. "
                        f"Choose a password not used in the last {history_count} changes."
                    ),
                )

    new_hash = hash_password(body.new_password)

    # Save current password to history before overwriting
    db.add(UserPasswordHistory(
        user_id=user.id,
        hashed_password=user.hashed_password,
        changed_at=now,
    ))

    user.hashed_password = new_hash
    user.force_password_change = False
    user.password_changed_at = now
    user.updated_at = now
    await db.commit()

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        user_id=user.id,
        username=user.username,
        action="change_password",
        target_type="user",
        target_id=str(user.id),
        ip_address=client_ip,
    )

    return {"detail": "Password changed successfully"}


# ---------------------------------------------------------------------------
# POST /auth/refresh  — issue a fresh token for an already-authenticated user
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Extend the session: validate the existing JWT, then return a brand-new
    JWT with a full expiry window.  The old token (jti) is superseded.
    """
    expire_hours = _get_int_setting("access_token_expire_hours", settings.ACCESS_TOKEN_EXPIRE_HOURS)
    single_session = gateway_settings.get(
        "single_session_per_user", str(settings.SINGLE_SESSION_PER_USER).lower()
    ) == "true"

    token, jti = create_access_token(
        data={
            "sub": str(current_user.id),
            "role": current_user.role,
            "username": current_user.username,
        },
        expires_delta=timedelta(hours=expire_hours),
    )

    if single_session:
        current_user.active_session_jti = jti
        await db.commit()

    return LoginResponse(
        token=token,
        force_password_change=current_user.force_password_change,
        user=UserOut(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            enabled=current_user.enabled,
            force_password_change=current_user.force_password_change,
            last_login=current_user.last_login,
            created_by=current_user.created_by,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        ),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------
@router.post("/logout")
async def logout(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="logout",
        target_type="session",
        target_id="",
        ip_address=client_ip,
    )
    return {"detail": "Logged out successfully"}
