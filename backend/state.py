"""
In-memory state management.

rate_limit_config  — keyed by api_key → {team_name, model, requests, window_sec,
                                          enabled, system_prompt}
request_log        — keyed by api_key → list of UTC timestamps (float)
dlp_patterns       — list of {name, pattern, severity, enabled, compiled}
gateway_settings   — keyed by setting name → string value
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Shared mutable state
# ---------------------------------------------------------------------------
rate_limit_config: Dict[str, dict] = {}
request_log: DefaultDict[str, List[float]] = defaultdict(list)
dlp_patterns: List[dict] = []
gateway_settings: Dict[str, str] = {}
# Per-key daily token usage: {api_key: {"date": "YYYY-MM-DD", "tokens": int}}.
# In-memory only — resets on restart (today's true total is recoverable from
# audit_logs if needed).
tokens_today: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Reload function called at startup and after any admin mutation
# ---------------------------------------------------------------------------
async def reload_memory(db: AsyncSession) -> None:
    """
    Reload all four in-memory structures from the database.
    Pre-compiles DLP regex patterns for performance.
    """
    from models import DLPPattern, GatewaySetting, Team  # noqa: PLC0415

    # ---- teams → rate_limit_config ----------------------------------------
    result = await db.execute(select(Team))
    teams = result.scalars().all()

    new_rl: Dict[str, dict] = {}
    for team in teams:
        new_rl[team.api_key] = {
            "team_name": team.team_name,
            "model": team.model,
            "requests": team.requests,
            "window_sec": team.window_sec,
            "enabled": team.enabled,
            "system_prompt": team.system_prompt,
            "expires_at": team.expires_at,
            "tokens_per_day": team.tokens_per_day,
            "data_classification": team.data_classification,
        }
    rate_limit_config.clear()
    rate_limit_config.update(new_rl)

    # ---- dlp_patterns -------------------------------------------------------
    result = await db.execute(select(DLPPattern))
    patterns = result.scalars().all()

    new_patterns: List[dict] = []
    for p in patterns:
        compiled = None
        if p.enabled:
            try:
                compiled = re.compile(p.pattern, re.IGNORECASE)
            except re.error:
                compiled = None  # skip broken patterns
        new_patterns.append(
            {
                "name": p.name,
                "pattern": p.pattern,
                "severity": p.severity,
                "enabled": p.enabled,
                "compiled": compiled,
                "action": p.action,
            }
        )
    dlp_patterns.clear()
    dlp_patterns.extend(new_patterns)

    # ---- gateway_settings ---------------------------------------------------
    result = await db.execute(select(GatewaySetting))
    settings_rows = result.scalars().all()

    new_settings: Dict[str, str] = {}
    for row in settings_rows:
        new_settings[row.key] = row.value
    gateway_settings.clear()
    gateway_settings.update(new_settings)

    # request_log is intentionally NOT reset here — it holds live sliding-
    # window data that should persist across reloads.
