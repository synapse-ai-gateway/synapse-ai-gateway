"""
Audit log admin endpoints.

GET /admin/audit        — paginated list with filters (analyst+)
GET /admin/audit/export — CSV export (analyst+)
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_role
from database import get_db
from utils import mask_api_key, mask_ip

router = APIRouter()


def _build_filters(
    model: type,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    team_name: Optional[str],
    statuses: Optional[List[str]],
) -> list:
    """Build SQLAlchemy filter list from request parameters."""
    filters = []
    if start_date:
        filters.append(model.timestamp >= start_date)
    if end_date:
        # Include the full end day
        filters.append(model.timestamp <= end_date)
    if team_name:
        filters.append(model.team_name.ilike(f"%{team_name}%"))
    if statuses:
        filters.append(model.status.in_(statuses))
    return filters


def _row_dict(log: Any) -> dict:
    return {
        "id": log.id,
        "api_key": mask_api_key(log.api_key),
        "team_name": log.team_name,
        "model": log.model,
        "status": log.status,
        "prompt_hash": log.prompt_hash,
        "response_status": log.response_status,
        "latency_ms": log.latency_ms,
        "auth_ms": log.auth_ms,
        "dlp_ms": log.dlp_ms,
        "inject_ms": log.inject_ms,
        "vllm_ms": log.vllm_ms,
        "dlp_flagged": log.dlp_flagged,
        "incident_id": log.incident_id,
        "tokens_used": log.tokens_used,
        "client_ip": mask_ip(log.client_ip),
        "timestamp": log.timestamp,
    }


# ---------------------------------------------------------------------------
# GET /admin/audit
# ---------------------------------------------------------------------------
@router.get("/audit")
async def list_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime]   = Query(None),
    team_name: Optional[str]       = Query(None),
    statuses:  Optional[List[str]] = Query(None),   # ?statuses=success&statuses=error
    page:      int                 = Query(1, ge=1),
    page_size: int                 = Query(20, ge=1, le=200),
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import AuditLog  # noqa: PLC0415

    where = _build_filters(AuditLog, start_date, end_date, team_name, statuses)

    base = select(AuditLog)
    if where:
        base = base.where(and_(*where))

    # Efficient COUNT
    count_q = select(func.count()).select_from(base.subquery())
    total: int = (await db.execute(count_q)).scalar_one()

    # Paginated rows
    rows_q = base.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = (await db.execute(rows_q)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": [_row_dict(log) for log in logs],
    }


# ---------------------------------------------------------------------------
# GET /admin/audit/export
# ---------------------------------------------------------------------------
@router.get("/audit/export")
async def export_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date:   Optional[datetime] = Query(None),
    team_name:  Optional[str]      = Query(None),
    statuses:   Optional[List[str]] = Query(None),
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from models import AuditLog  # noqa: PLC0415

    where = _build_filters(AuditLog, start_date, end_date, team_name, statuses)
    q = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if where:
        q = q.where(and_(*where))

    logs = (await db.execute(q)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "api_key", "team_name", "model", "status", "prompt_hash",
        "response_status", "latency_ms", "auth_ms", "dlp_ms", "inject_ms",
        "vllm_ms", "dlp_flagged", "incident_id", "tokens_used", "client_ip", "timestamp",
    ])
    for log in logs:
        writer.writerow([
            log.id, mask_api_key(log.api_key), log.team_name, log.model, log.status,
            log.prompt_hash, log.response_status, log.latency_ms,
            log.auth_ms, log.dlp_ms, log.inject_ms, log.vllm_ms,
            log.dlp_flagged, log.incident_id or "", log.tokens_used or "",
            mask_ip(log.client_ip),
            log.timestamp.isoformat() if log.timestamp else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
