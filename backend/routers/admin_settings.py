"""
Admin Settings router — GET and PATCH /admin/settings
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_role
from database import get_db
from models import GatewaySetting, UserActivityLog
from state import reload_memory

router = APIRouter()

SENSITIVE_KEYS = {"JWT_SECRET", "ADMIN_PASSWORD"}


@router.get("/settings")
async def get_settings(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(GatewaySetting))
    rows = result.scalars().all()
    return {
        row.key: row.value
        for row in rows
        if row.key not in SENSITIVE_KEYS
    }


@router.patch("/settings")
async def update_settings(
    body: dict,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No settings provided.")

    # Reject attempts to write sensitive keys
    for k in SENSITIVE_KEYS:
        if k in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update sensitive key '{k}' via this endpoint.",
            )

    # Only allow updating settings that already exist (seeded). This blocks
    # injection of arbitrary keys into the gateway_settings table.
    known_keys = set(
        (await db.execute(select(GatewaySetting.key))).scalars().all()
    )
    unknown = [k for k in body if k not in known_keys]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown setting key(s): {', '.join(sorted(unknown))}.",
        )

    changes: dict = {}
    now = datetime.utcnow()

    for key, value in body.items():
        result = await db.execute(select(GatewaySetting).where(GatewaySetting.key == key))
        row = result.scalars().first()
        if row:
            old_value = row.value
            row.value = str(value)
            row.updated_by = current_user.id
            row.updated_at = now
            changes[key] = {"before": old_value, "after": str(value)}
        else:
            new_row = GatewaySetting(
                key=key,
                value=str(value),
                updated_by=current_user.id,
                updated_at=now,
            )
            db.add(new_row)
            changes[key] = {"before": None, "after": str(value)}

    # Activity log
    db.add(
        UserActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action="settings.update",
            target_type="settings",
            target_id="gateway_settings",
            changes=changes,
            ip_address=request.client.host if request.client else None,
            timestamp=now,
        )
    )

    await db.commit()
    await reload_memory(db)

    result = await db.execute(select(GatewaySetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows if row.key not in SENSITIVE_KEYS}
