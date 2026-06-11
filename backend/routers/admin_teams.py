"""
Admin teams management.

GET    /admin/teams           — list all (analyst+), mask api_key
POST   /admin/teams           — create (admin+), return full api_key
PATCH  /admin/teams/{api_key} — update (admin+)
DELETE /admin/teams/{api_key} — soft delete (admin+)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_role
from constants import CLASSIFICATION_VALUES, DataClassification
from database import get_db
from state import reload_memory
from utils import mask_api_key

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TeamCreate(BaseModel):
    team_name: str
    model: str
    requests: int = Field(default=10, ge=1)
    window_sec: int = Field(default=60, ge=1)
    system_prompt: Optional[str] = None
    expires_at: Optional[datetime] = None
    tokens_per_day: Optional[int] = Field(default=None, ge=1)
    data_classification: str = Field(default=DataClassification.SENSITIVE)


class TeamUpdate(BaseModel):
    team_name: Optional[str] = None
    model: Optional[str] = None
    requests: Optional[int] = Field(default=None, ge=1)
    window_sec: Optional[int] = Field(default=None, ge=1)
    enabled: Optional[bool] = None
    system_prompt: Optional[str] = None
    expires_at: Optional[datetime] = None
    tokens_per_day: Optional[int] = Field(default=None, ge=1)
    data_classification: Optional[str] = None


def _validate_classification(value: str) -> None:
    if value not in CLASSIFICATION_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data_classification '{value}'. Allowed: "
                   f"{', '.join(sorted(CLASSIFICATION_VALUES))}.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
# GET /admin/teams
# ---------------------------------------------------------------------------
@router.get("/teams")
async def list_teams(
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from models import Team  # noqa: PLC0415

    result = await db.execute(select(Team).order_by(Team.team_name))
    teams = result.scalars().all()

    return [
        {
            "id": t.id,
            "api_key": mask_api_key(t.api_key),
            "team_name": t.team_name,
            "model": t.model,
            "requests": t.requests,
            "window_sec": t.window_sec,
            "enabled": t.enabled,
            "system_prompt": t.system_prompt,
            "expires_at": t.expires_at,
            "tokens_per_day": t.tokens_per_day,
            "data_classification": t.data_classification,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in teams
    ]


# ---------------------------------------------------------------------------
# POST /admin/teams
# ---------------------------------------------------------------------------
@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import Team  # noqa: PLC0415

    _validate_classification(body.data_classification)

    api_key = str(uuid.uuid4())
    now = datetime.utcnow()
    team = Team(
        api_key=api_key,
        team_name=body.team_name,
        model=body.model,
        requests=body.requests,
        window_sec=body.window_sec,
        system_prompt=body.system_prompt,
        expires_at=body.expires_at,
        tokens_per_day=body.tokens_per_day,
        data_classification=body.data_classification,
        enabled=True,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="create_team",
        target_type="team",
        target_id=api_key,
        ip_address=client_ip,
        changes={"team_name": body.team_name, "model": body.model},
    )

    return {
        "id": team.id,
        "api_key": api_key,  # Return full key on creation
        "team_name": team.team_name,
        "model": team.model,
        "requests": team.requests,
        "window_sec": team.window_sec,
        "enabled": team.enabled,
        "system_prompt": team.system_prompt,
        "expires_at": team.expires_at,
        "tokens_per_day": team.tokens_per_day,
        "data_classification": team.data_classification,
        "created_at": team.created_at,
    }


# ---------------------------------------------------------------------------
# GET /admin/teams/{team_id}/api-key  — reveal full key (admin+, logged)
# ---------------------------------------------------------------------------
@router.get("/teams/{team_id}/api-key")
async def get_team_api_key(
    team_id: int,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import Team  # noqa: PLC0415

    result = await db.execute(select(Team).where(Team.id == team_id))
    team: Team | None = result.scalars().first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="reveal_api_key",
        target_type="team",
        target_id=str(team_id),
        ip_address=client_ip,
        changes={"team_name": team.team_name},
    )

    return {"api_key": team.api_key}


# ---------------------------------------------------------------------------
# PATCH /admin/teams/{team_id}
# ---------------------------------------------------------------------------
@router.patch("/teams/{team_id}")
async def update_team(
    team_id: int,
    body: TeamUpdate,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import Team  # noqa: PLC0415

    result = await db.execute(select(Team).where(Team.id == team_id))
    team: Team | None = result.scalars().first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    changes: dict = {}
    if body.team_name is not None and body.team_name != team.team_name:
        changes["team_name"] = {"old": team.team_name, "new": body.team_name}
        team.team_name = body.team_name
    if body.model is not None and body.model != team.model:
        changes["model"] = {"old": team.model, "new": body.model}
        team.model = body.model
    if body.requests is not None and body.requests != team.requests:
        changes["requests"] = {"old": team.requests, "new": body.requests}
        team.requests = body.requests
    if body.window_sec is not None and body.window_sec != team.window_sec:
        changes["window_sec"] = {"old": team.window_sec, "new": body.window_sec}
        team.window_sec = body.window_sec
    if body.enabled is not None and body.enabled != team.enabled:
        changes["enabled"] = {"old": team.enabled, "new": body.enabled}
        team.enabled = body.enabled
    if body.system_prompt is not None and body.system_prompt != team.system_prompt:
        changes["system_prompt"] = {"old": team.system_prompt, "new": body.system_prompt}
        team.system_prompt = body.system_prompt
    if body.expires_at is not None and body.expires_at != team.expires_at:
        changes["expires_at"] = {
            "old": team.expires_at.isoformat() if team.expires_at else None,
            "new": body.expires_at.isoformat(),
        }
        team.expires_at = body.expires_at
    if body.tokens_per_day is not None and body.tokens_per_day != team.tokens_per_day:
        changes["tokens_per_day"] = {"old": team.tokens_per_day, "new": body.tokens_per_day}
        team.tokens_per_day = body.tokens_per_day
    if body.data_classification is not None and body.data_classification != team.data_classification:
        _validate_classification(body.data_classification)
        changes["data_classification"] = {
            "old": team.data_classification,
            "new": body.data_classification,
        }
        team.data_classification = body.data_classification

    team.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(team)

    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="update_team",
        target_type="team",
        target_id=str(team_id),
        ip_address=client_ip,
        changes=changes,
    )

    return {
        "id": team.id,
        "api_key": mask_api_key(team.api_key),
        "team_name": team.team_name,
        "model": team.model,
        "requests": team.requests,
        "window_sec": team.window_sec,
        "enabled": team.enabled,
        "system_prompt": team.system_prompt,
        "expires_at": team.expires_at,
        "tokens_per_day": team.tokens_per_day,
        "data_classification": team.data_classification,
        "updated_at": team.updated_at,
    }


# ---------------------------------------------------------------------------
# DELETE /admin/teams/{team_id}  (soft delete / toggle enabled)
# ---------------------------------------------------------------------------
@router.delete("/teams/{team_id}", status_code=status.HTTP_200_OK)
async def delete_team(
    team_id: int,
    request: Request,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import Team  # noqa: PLC0415

    result = await db.execute(select(Team).where(Team.id == team_id))
    team: Team | None = result.scalars().first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    team.enabled = False
    team.updated_at = datetime.utcnow()
    await db.commit()

    await reload_memory(db)

    client_ip = request.client.host if request.client else None
    await _log_activity(
        db,
        current_user,
        action="disable_team",
        target_type="team",
        target_id=str(team_id),
        ip_address=client_ip,
        changes={"enabled": {"old": True, "new": False}},
    )

    return {"detail": f"Team '{team.team_name}' disabled successfully"}
