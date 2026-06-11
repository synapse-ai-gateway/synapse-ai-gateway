"""
JWT authentication and authorization utilities.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db

if TYPE_CHECKING:
    from models import User

# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------
ROLE_HIERARCHY: dict[str, int] = {
    "readonly": 0,
    "analyst": 1,
    "admin": 2,
    "superadmin": 3,
}

ALGORITHM = settings.JWT_ALGORITHM

# Bearer token extractor (auto_error=True raises 401 automatically)
_bearer_scheme = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt (cost factor from BCRYPT_ROUNDS)."""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    ).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str]:
    """
    Create a signed JWT access token.
    Returns (token, jti) — the caller stores jti on the user row for
    single-session enforcement (§6.4).
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    )
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "jti": jti})
    token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return token, jti


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> "User":
    """
    Decode JWT, load the corresponding User row, check enabled=True.
    Returns the User ORM object.
    Raises HTTP 401 on any failure.
    """
    # Import here to avoid circular import at module level
    from models import User  # noqa: PLC0415

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.JWT_SECRET, algorithms=[ALGORITHM]
        )
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
        jti: Optional[str] = payload.get("jti")
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception
    if not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # §6.4 Single session — reject tokens whose jti no longer matches
    from state import gateway_settings  # noqa: PLC0415
    if gateway_settings.get(
        "single_session_per_user", str(settings.SINGLE_SESSION_PER_USER).lower()
    ) == "true":
        if jti and user.active_session_jti and user.active_session_jti != jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session superseded by a newer login. Please sign in again.",
            )

    return user


def require_role(minimum_role: str) -> Callable:
    """
    Return a FastAPI dependency that enforces role >= minimum_role.

    Usage:
        @router.get("/admin/something", dependencies=[Depends(require_role("admin"))])
    or:
        current_user: User = Depends(require_role("admin"))
    """

    async def _checker(current_user: "User" = Depends(get_current_user)) -> "User":
        user_level = ROLE_HIERARCHY.get(current_user.role, -1)
        required_level = ROLE_HIERARCHY.get(minimum_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher. Your role: '{current_user.role}'",
            )
        return current_user

    return _checker


# ---------------------------------------------------------------------------
# Password strength validation
# ---------------------------------------------------------------------------
_SPECIAL_CHARS = re.compile(r'[!@#$%^&*()\-_=+\[\]{}|;:\'",.<>?/`~\\]')


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password complexity.

    Returns (True, "") on success, (False, reason) on failure.

    Rules:
    - Minimum length from PASSWORD_MIN_LENGTH
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return (
            False,
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long.",
        )
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not _SPECIAL_CHARS.search(password):
        return False, "Password must contain at least one special character."
    return True, ""
