"""
Statistics admin endpoints.

GET /admin/stats/summary   — today's summary (analyst+)
GET /admin/stats/per-team  — per-team request counts (last 60 min) (analyst+)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import state
from auth import require_role
from constants import AuditStatus
from database import get_db
from utils import mask_api_key

router = APIRouter()

# Sliding-window length for the per-team request-rate view.
_STATS_WINDOW_SECONDS = 60 * 60


# ---------------------------------------------------------------------------
# GET /admin/stats/summary
# ---------------------------------------------------------------------------
@router.get("/stats/summary")
async def stats_summary(
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import AuditLog, Team  # noqa: PLC0415

    # Current UTC day boundaries
    now_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # Convert to naive for comparison (DB stores naive UTC)
    day_start = now_utc.replace(tzinfo=None)

    # Total requests today
    total_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= day_start)
    )
    total_requests_today: int = total_result.scalar() or 0

    # DLP blocks today
    dlp_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.timestamp >= day_start,
                AuditLog.status == AuditStatus.BLOCKED_DLP,
            )
        )
    )
    dlp_blocks_today: int = dlp_result.scalar() or 0

    # Rate limit hits today
    rl_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.timestamp >= day_start,
                AuditLog.status == AuditStatus.BLOCKED_RATE_LIMIT,
            )
        )
    )
    rate_limit_hits_today: int = rl_result.scalar() or 0

    # Active teams
    active_result = await db.execute(
        select(func.count(Team.id)).where(Team.enabled == True)  # noqa: E712
    )
    active_teams: int = active_result.scalar() or 0

    return {
        "total_requests_today": total_requests_today,
        "dlp_blocks_today": dlp_blocks_today,
        "rate_limit_hits_today": rate_limit_hits_today,
        "active_teams": active_teams,
        "as_of": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /admin/stats/per-team
# ---------------------------------------------------------------------------
@router.get("/stats/per-team")
async def stats_per_team(
    current_user=Depends(require_role("analyst")),
) -> dict:
    """
    Returns per-team request counts from the in-memory sliding window.
    Uses the last 60 minutes of data from state.request_log.
    """
    now_ts = time.time()

    per_team: dict[str, dict] = {}
    for api_key, timestamps in state.request_log.items():
        recent = [ts for ts in timestamps if now_ts - ts <= _STATS_WINDOW_SECONDS]
        team_name = "unknown"
        team_cfg = state.rate_limit_config.get(api_key)
        if team_cfg:
            team_name = team_cfg["team_name"]

        per_team[api_key] = {
            "api_key_masked": mask_api_key(api_key),
            "team_name": team_name,
            "requests_last_60min": len(recent),
        }

    # Sort by descending count
    sorted_teams = sorted(
        per_team.values(), key=lambda x: x["requests_last_60min"], reverse=True
    )
    return {"window_minutes": _STATS_WINDOW_SECONDS // 60, "teams": sorted_teams}
