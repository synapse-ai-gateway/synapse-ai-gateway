"""
Database seeding — runs on application startup if the database is empty.

Creates:
  - 1 superadmin user (forced to change password on first login)
  - DLP patterns loaded from DLP_PATTERNS_FILE
  - Default gateway_settings (seeded from environment-backed config)

Teams are NOT auto-seeded — their api_keys are credentials, and printing them
to stdout means they end up in `docker logs` indefinitely. The admin creates
teams via the UI / `POST /admin/teams` after first login, where the api_key is
returned exactly once in the HTTP response and masked everywhere else.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password
from config import settings

logger = logging.getLogger(__name__)


def _load_dlp_definitions() -> list[dict]:
    """
    Load the initial DLP category definitions from DLP_PATTERNS_FILE.

    The file is a JSON array of objects: {"name", "pattern", "severity"}.
    Returns an empty list (with a warning) if the file is missing or invalid,
    so a misconfiguration never crashes startup.
    """
    path = Path(settings.DLP_PATTERNS_FILE)
    if not path.is_file():
        logger.warning("DLP patterns file not found: %s. Seeding no DLP patterns.", path)
        return []
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read DLP patterns file %s: %s. Seeding none.", path, exc)
        return []
    if not isinstance(data, list):
        logger.warning("DLP patterns file %s must contain a JSON array. Seeding none.", path)
        return []
    return data


async def seed_database(db: AsyncSession) -> None:
    """
    Seed initial data only when the users table is empty.
    Prints generated API keys to stdout.
    """
    from models import DLPPattern, GatewaySetting, User  # noqa: PLC0415

    # ------------------------------------------------------------------ guard
    result = await db.execute(select(User).limit(1))
    if result.scalars().first() is not None:
        return  # Already seeded

    logger.info("Seeding database with initial data…")

    now = datetime.utcnow()

    # -------------------------------------------------------------- superadmin
    admin = User(
        username="admin",
        email="admin@yourorg.com",
        full_name="System Administrator",
        hashed_password=hash_password(settings.ADMIN_PASSWORD),
        role="superadmin",
        enabled=True,
        force_password_change=True,
        created_at=now,
        updated_at=now,
    )
    db.add(admin)
    await db.flush()  # Populate admin.id before FK references

    # Teams are intentionally NOT seeded — see the module docstring. The admin
    # creates them post-login via the UI / POST /admin/teams, where the api_key
    # appears once in the HTTP response and never in any log.

    # --------------------------------------------------------------- DLP patterns
    # Definitions live in an external config file (DLP_PATTERNS_FILE), never in
    # source. If the file is missing, no patterns are seeded and a warning is
    # printed — DLP can still be configured via the admin API afterwards.
    dlp_definitions = _load_dlp_definitions()

    for p in dlp_definitions:
        pattern_row = DLPPattern(
            name=p["name"],
            pattern=p["pattern"],
            severity=p["severity"],
            action=p.get("action", "block"),
            enabled=True,
            created_by=admin.id,
            created_at=now,
        )
        db.add(pattern_row)

    # --------------------------------------------------------------- gateway settings
    # Initial values seeded from environment-backed settings (see config.py /
    # .env.example). After seeding these are editable via the admin API.
    gateway_settings_data = {
        # ── Gateway ────────────────────────────────────────────────────────────
        "vllm_url": settings.VLLM_URL,
        "default_model": settings.DEFAULT_MODEL,
        "timeout_sec": str(settings.LLM_REQUEST_TIMEOUT_SEC),
        "default_requests": str(settings.DEFAULT_REQUESTS),
        "default_window_sec": str(settings.DEFAULT_WINDOW_SEC),
        "default_system_prompt": settings.DEFAULT_SYSTEM_PROMPT,
        # ── Session / Token ────────────────────────────────────────────────────
        "access_token_expire_hours": str(settings.ACCESS_TOKEN_EXPIRE_HOURS),
        "session_warning_minutes": str(settings.SESSION_WARNING_MINUTES),   # §6.6
        "single_session_per_user": str(settings.SINGLE_SESSION_PER_USER).lower(),  # §6.4
        # ── Account Lockout (§3.1) ─────────────────────────────────────────────
        "max_failed_logins": str(settings.MAX_FAILED_LOGINS),
        "lockout_minutes": str(settings.LOCKOUT_MINUTES),
        # ── Password Policy (§3.1) ─────────────────────────────────────────────
        "min_password_age_days": str(settings.MIN_PASSWORD_AGE_DAYS),
        "max_password_age_days": str(settings.MAX_PASSWORD_AGE_DAYS),
        "password_history_count": str(settings.PASSWORD_HISTORY_COUNT),
        # ── Inactivity (§3.2) ─────────────────────────────────────────────────
        "inactivity_disable_days": str(settings.INACTIVITY_DISABLE_DAYS),
    }

    for key, value in gateway_settings_data.items():
        setting_row = GatewaySetting(
            key=key,
            value=value,
            updated_by=admin.id,
            updated_at=now,
        )
        db.add(setting_row)

    await db.commit()
    logger.info("Seeding complete.")
