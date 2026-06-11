"""
DLP Incidents admin endpoints.

GET /admin/incidents        — paginated list with filters (analyst+)
GET /admin/incidents/export — CSV export of filtered results (analyst+)
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_role
from database import get_db
from utils import mask_api_key, mask_ip

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /admin/incidents
# ---------------------------------------------------------------------------
@router.get("/incidents")
async def list_incidents(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    severity: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    incident_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from models import DLPIncident  # noqa: PLC0415

    filters = []
    if from_date:
        filters.append(DLPIncident.timestamp >= from_date)
    if to_date:
        filters.append(DLPIncident.timestamp <= to_date)
    if severity:
        filters.append(DLPIncident.max_severity == severity)
    if team:
        filters.append(DLPIncident.team_name == team)
    if incident_id:
        filters.append(DLPIncident.incident_id == incident_id)

    base_query = select(DLPIncident)
    if filters:
        base_query = base_query.where(and_(*filters))

    # Count total (DB-side COUNT — never load all rows into memory)
    count_query = select(func.count()).select_from(base_query.subquery())
    total: int = (await db.execute(count_query)).scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    paginated_query = (
        base_query.order_by(DLPIncident.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(paginated_query)
    incidents = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": inc.id,
                "incident_id": inc.incident_id,
                "api_key": mask_api_key(inc.api_key),
                "team_name": inc.team_name,
                "client_ip": mask_ip(inc.client_ip),
                "patterns": inc.patterns,
                "severities": inc.severities,
                "max_severity": inc.max_severity,
                "match_counts": inc.match_counts,
                "message_len": inc.message_len,
                "source": inc.source,
                "timestamp": inc.timestamp,
            }
            for inc in incidents
        ],
    }


# ---------------------------------------------------------------------------
# GET /admin/incidents/export
# ---------------------------------------------------------------------------
@router.get("/incidents/export")
async def export_incidents(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    severity: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    incident_id: Optional[str] = Query(None),
    current_user=Depends(require_role("analyst")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    from models import DLPIncident  # noqa: PLC0415

    filters = []
    if from_date:
        filters.append(DLPIncident.timestamp >= from_date)
    if to_date:
        filters.append(DLPIncident.timestamp <= to_date)
    if severity:
        filters.append(DLPIncident.max_severity == severity)
    if team:
        filters.append(DLPIncident.team_name == team)
    if incident_id:
        filters.append(DLPIncident.incident_id == incident_id)

    base_query = select(DLPIncident).order_by(DLPIncident.timestamp.desc())
    if filters:
        base_query = base_query.where(and_(*filters))

    result = await db.execute(base_query)
    incidents = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "incident_id",
            "api_key",
            "team_name",
            "client_ip",
            "patterns",
            "severities",
            "max_severity",
            "match_counts",
            "message_len",
            "source",
            "timestamp",
        ]
    )
    for inc in incidents:
        writer.writerow(
            [
                inc.incident_id,
                mask_api_key(inc.api_key),
                inc.team_name,
                mask_ip(inc.client_ip),
                "|".join(inc.patterns) if isinstance(inc.patterns, list) else inc.patterns,
                "|".join(inc.severities) if isinstance(inc.severities, list) else inc.severities,
                inc.max_severity,
                str(inc.match_counts),
                inc.message_len,
                inc.source,
                inc.timestamp.isoformat() if inc.timestamp else "",
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=dlp_incidents.csv"
        },
    )
