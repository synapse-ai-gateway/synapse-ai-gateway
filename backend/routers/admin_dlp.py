"""
DLP pattern management.

GET    /admin/dlp-patterns          — list (analyst+)
POST   /admin/dlp-patterns          — create (admin+)
PATCH  /admin/dlp-patterns/{name}   — update (admin+)
DELETE /admin/dlp-patterns/{name}   — delete (superadmin)
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_role
from constants import DLP_ACTION_VALUES, SEVERITY_VALUES, DLPAction
from database import get_db
from state import reload_memory

router = APIRouter()


def _validate_severity(severity: str) -> None:
    if severity not in SEVERITY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity '{severity}'. Allowed: {', '.join(sorted(SEVERITY_VALUES))}.",
        )


def _validate_action(action: str) -> None:
    if action not in DLP_ACTION_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{action}'. Allowed: "
                   f"{', '.join(sorted(DLP_ACTION_VALUES))}.",
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class DLPPatternCreate(BaseModel):
    name: str
    pattern: str
    severity: str  # Critical | High | Medium | Low
    action: str = DLPAction.BLOCK  # block | redact | alert


class DLPPatternUpdate(BaseModel):
    pattern: Optional[str] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None
    action: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_regex(pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid regular expression: {exc}",
        )


async def _log_activity(
    db: AsyncSession,
    user,
    action: str,
    target_type: str,
    target_id: str,
    ip_address: str | None = None,
    changes: dict | None = None,
) -> None:
    from models import UserActivityLog  # noqa: PLC0415

    log = UserActivityLog(
        user_id=user.id,
        username=user.username,
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
# GET /admin/dlp-patterns
# ---------------------------------------------------------------------------
@router.get("/dlp-patterns")
async def list_dlp_patterns(
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from models import DLPPattern  # noqa: PLC0415

    result = await db.execute(select(DLPPattern).order_by(DLPPattern.name))
    patterns = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "pattern": p.pattern,
            "severity": p.severity,
            "action": p.action,
            "enabled": p.enabled,
            "created_at": p.created_at,
        }
        for p in patterns
    ]


# ---------------------------------------------------------------------------
# POST /admin/dlp-patterns
# ---------------------------------------------------------------------------
@router.post("/dlp-patterns", status_code=status.HTTP_201_CREATED)
async def create_dlp_pattern(
    body: DLPPatternCreate,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import DLPPattern  # noqa: PLC0415

    _validate_regex(body.pattern)
    _validate_severity(body.severity)
    _validate_action(body.action)

    # Check duplicate name
    result = await db.execute(
        select(DLPPattern).where(DLPPattern.name == body.name)
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DLP pattern '{body.name}' already exists",
        )

    pattern_row = DLPPattern(
        name=body.name,
        pattern=body.pattern,
        severity=body.severity,
        action=body.action,
        enabled=True,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(pattern_row)
    await db.commit()
    await db.refresh(pattern_row)

    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="create_dlp_pattern",
        target_type="dlp_pattern",
        target_id=body.name,
        ip_address=client_ip,
        changes={"name": body.name, "severity": body.severity},
    )

    return {
        "id": pattern_row.id,
        "name": pattern_row.name,
        "pattern": pattern_row.pattern,
        "severity": pattern_row.severity,
        "action": pattern_row.action,
        "enabled": pattern_row.enabled,
        "created_at": pattern_row.created_at,
    }


# ---------------------------------------------------------------------------
# PATCH /admin/dlp-patterns/{name}
# ---------------------------------------------------------------------------
@router.patch("/dlp-patterns/{name}")
async def update_dlp_pattern(
    name: str,
    body: DLPPatternUpdate,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import DLPPattern  # noqa: PLC0415

    result = await db.execute(
        select(DLPPattern).where(DLPPattern.name == name)
    )
    pattern_row: DLPPattern | None = result.scalars().first()
    if pattern_row is None:
        raise HTTPException(status_code=404, detail=f"DLP pattern '{name}' not found")

    changes: dict = {}
    if body.pattern is not None:
        _validate_regex(body.pattern)
        changes["pattern"] = "updated"
        pattern_row.pattern = body.pattern
    if body.severity is not None:
        _validate_severity(body.severity)
        changes["severity"] = {"old": pattern_row.severity, "new": body.severity}
        pattern_row.severity = body.severity
    if body.action is not None:
        _validate_action(body.action)
        changes["action"] = {"old": pattern_row.action, "new": body.action}
        pattern_row.action = body.action
    if body.enabled is not None:
        changes["enabled"] = {"old": pattern_row.enabled, "new": body.enabled}
        pattern_row.enabled = body.enabled

    await db.commit()
    await db.refresh(pattern_row)
    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="update_dlp_pattern",
        target_type="dlp_pattern",
        target_id=name,
        ip_address=client_ip,
        changes=changes,
    )

    return {
        "id": pattern_row.id,
        "name": pattern_row.name,
        "pattern": pattern_row.pattern,
        "severity": pattern_row.severity,
        "action": pattern_row.action,
        "enabled": pattern_row.enabled,
        "created_at": pattern_row.created_at,
    }


# ---------------------------------------------------------------------------
# DELETE /admin/dlp-patterns/{name}
# ---------------------------------------------------------------------------
@router.delete("/dlp-patterns/{name}")
async def delete_dlp_pattern(
    name: str,
    request: Request,
    current_user=Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import DLPPattern  # noqa: PLC0415

    result = await db.execute(
        select(DLPPattern).where(DLPPattern.name == name)
    )
    pattern_row: DLPPattern | None = result.scalars().first()
    if pattern_row is None:
        raise HTTPException(status_code=404, detail=f"DLP pattern '{name}' not found")

    await db.delete(pattern_row)
    await db.commit()
    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="delete_dlp_pattern",
        target_type="dlp_pattern",
        target_id=name,
        ip_address=client_ip,
    )

    return {"detail": f"DLP pattern '{name}' deleted"}
