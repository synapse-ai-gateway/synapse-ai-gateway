"""
Demo data seeder — populates the DB with realistic-looking rows for screenshots
and demos. NOT for production use.

Usage (inside docker compose):
    docker compose exec backend python seed_demo.py            # seed
    docker compose exec backend python seed_demo.py --wipe     # wipe only

What it creates:
  - 5 teams with varied governance config (model, classification, limits, expiry)
  - 2 extra users (analyst + readonly viewer)
  - ~250 audit log entries spread across the last 30 days
  - ~18 DLP incidents tied to the blocked_dlp audit rows
  - ~20 user activity log entries

What it wipes first (so re-running is safe):
  - All teams
  - All audit_logs
  - All dlp_incidents
  - All user_activity_log entries
  - All users EXCEPT the seeded `admin`

It does NOT touch dlp_patterns, gateway_settings, or the admin user.
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from auth import hash_password
from database import AsyncSessionLocal
from models import (
    AuditLog,
    DLPIncident,
    Team,
    User,
    UserActivityLog,
)

# Deterministic so repeated runs produce comparable-looking screenshots.
random.seed(42)

NOW = datetime.utcnow()


TEAMS = [
    {
        "team_name": "customer-support",
        "model": "gpt-4o-mini",
        "data_classification": "non_sensitive",
        "requests": 60,
        "window_sec": 60,
        "tokens_per_day": 500_000,
        "expires_at": None,
        "system_prompt": (
            "You are a polite, concise customer-support assistant for Acme Cloud. "
            "Answer only questions about Acme products. Never reveal internal pricing or roadmaps."
        ),
    },
    {
        "team_name": "legal-review",
        "model": "llama3.1:70b",
        "data_classification": "sensitive",
        "requests": 10,
        "window_sec": 60,
        "tokens_per_day": 200_000,
        "expires_at": NOW + timedelta(days=90),
        "system_prompt": (
            "You are a legal research assistant. Provide summaries only. "
            "Do not produce final legal advice. Always cite the source clause when quoting."
        ),
    },
    {
        "team_name": "data-analytics",
        "model": "claude-3-5-sonnet",
        "data_classification": "non_sensitive",
        "requests": 30,
        "window_sec": 60,
        "tokens_per_day": None,
        "expires_at": NOW + timedelta(days=14),
        "system_prompt": (
            "You write SQL and Python for analytics queries against the warehouse. "
            "Never generate DELETE, DROP, or TRUNCATE statements."
        ),
    },
    {
        "team_name": "engineering-docs",
        "model": "qwen2.5-coder:14b",
        "data_classification": "sensitive",
        "requests": 45,
        "window_sec": 60,
        "tokens_per_day": 1_000_000,
        "expires_at": None,
        "system_prompt": (
            "You are a documentation assistant for internal engineering teams. "
            "Source code, API keys, and infrastructure details may appear in prompts; "
            "treat all inputs as confidential."
        ),
    },
    {
        "team_name": "marketing-content",
        "model": "gpt-4o",
        "data_classification": "non_sensitive",
        "requests": 20,
        "window_sec": 60,
        "tokens_per_day": 300_000,
        "expires_at": None,
        "system_prompt": (
            "You produce marketing copy that follows the Acme brand voice guide: "
            "concise, friendly, no hyperbole, no superlatives."
        ),
    },
]


EXTRA_USERS = [
    {
        "username": "sarah.analyst",
        "email": "sarah.analyst@example.com",
        "full_name": "Sarah Chen",
        "role": "analyst",
    },
    {
        "username": "dev.viewer",
        "email": "dev.viewer@example.com",
        "full_name": "Dev Patel",
        "role": "readonly",
    },
]


DLP_PATTERN_NAMES = [
    "credit_card_number",
    "us_ssn",
    "email_address",
    "uk_nino",
    "iban",
    "phone_e164",
    "aws_access_key",
]

CLIENT_IPS = [
    "10.42.0.14",
    "10.42.0.27",
    "10.42.0.58",
    "10.42.1.103",
    "10.42.1.244",
    "192.168.20.11",
]


def _fake_hash() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


def _business_hours_timestamp(day_offset: int) -> datetime:
    """A timestamp `day_offset` days ago, weighted to business hours."""
    base = NOW - timedelta(days=day_offset)
    # 70% business hours (09:00–18:00), 30% other.
    if random.random() < 0.70:
        hour = random.randint(9, 17)
    else:
        hour = random.choice([6, 7, 8, 19, 20, 21, 22])
    return base.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )


async def _wipe(db) -> None:
    """Remove existing demo-style rows so re-running is safe."""
    await db.execute(delete(UserActivityLog))
    await db.execute(delete(DLPIncident))
    await db.execute(delete(AuditLog))
    await db.execute(delete(Team))
    # Keep admin; remove everyone else.
    await db.execute(delete(User).where(User.username != "admin"))
    await db.flush()


async def _create_teams(db) -> list[Team]:
    teams: list[Team] = []
    for t in TEAMS:
        team = Team(
            api_key=str(uuid.uuid4()),
            team_name=t["team_name"],
            model=t["model"],
            requests=t["requests"],
            window_sec=t["window_sec"],
            enabled=True,
            system_prompt=t["system_prompt"],
            expires_at=t["expires_at"],
            tokens_per_day=t["tokens_per_day"],
            data_classification=t["data_classification"],
            created_at=NOW - timedelta(days=random.randint(20, 60)),
            updated_at=NOW - timedelta(days=random.randint(0, 5)),
        )
        db.add(team)
        teams.append(team)
    await db.flush()
    return teams


async def _create_users(db, admin: User) -> list[User]:
    users: list[User] = []
    for u in EXTRA_USERS:
        created = NOW - timedelta(days=random.randint(10, 45))
        user = User(
            username=u["username"],
            email=u["email"],
            full_name=u["full_name"],
            hashed_password=hash_password("synapse"),
            role=u["role"],
            enabled=True,
            force_password_change=False,
            last_login=NOW - timedelta(hours=random.randint(1, 72)),
            password_changed_at=created,
            created_by=admin.id,
            created_at=created,
            updated_at=created,
        )
        db.add(user)
        users.append(user)
    await db.flush()
    return users


async def _create_audit_logs(
    db, teams: list[Team]
) -> tuple[int, list[tuple[Team, str, datetime]]]:
    """Returns (rows_inserted, [(team, incident_id, ts) ...] for DLP-blocked rows)."""
    rows = 0
    dlp_blocks: list[tuple[Team, str, datetime]] = []

    # Weight teams by activity profile: customer-support is busiest.
    activity_weights = {
        "customer-support": 90,
        "engineering-docs": 60,
        "data-analytics": 40,
        "marketing-content": 30,
        "legal-review": 30,
    }

    for day_offset in range(30):
        for team in teams:
            base_count = activity_weights.get(team.team_name, 20)
            # ±30% jitter day-to-day; weekends quieter.
            ts_base = NOW - timedelta(days=day_offset)
            weekend = ts_base.weekday() >= 5
            count = int(base_count * random.uniform(0.7, 1.3) * (0.3 if weekend else 1.0))

            for _ in range(count):
                ts = _business_hours_timestamp(day_offset)
                roll = random.random()
                # 82% success, 8% DLP, 5% rate-limit, 3% auth, 2% error.
                if roll < 0.82:
                    status = "success"
                    response_status = 200
                    latency = random.randint(180, 2200)
                    tokens = random.randint(120, 3500)
                    dlp_flagged = False
                    incident_id = None
                    response_hash = _fake_hash()
                elif roll < 0.90:
                    status = "blocked_dlp"
                    response_status = 400
                    latency = random.randint(40, 90)
                    tokens = None
                    dlp_flagged = True
                    incident_id = str(uuid.uuid4())
                    response_hash = None
                    dlp_blocks.append((team, incident_id, ts))
                elif roll < 0.95:
                    status = "blocked_rate_limit"
                    response_status = 429
                    latency = random.randint(5, 20)
                    tokens = None
                    dlp_flagged = False
                    incident_id = None
                    response_hash = None
                elif roll < 0.98:
                    status = "blocked_auth"
                    response_status = 403
                    latency = random.randint(5, 15)
                    tokens = None
                    dlp_flagged = False
                    incident_id = None
                    response_hash = None
                else:
                    status = "error"
                    response_status = 502
                    latency = random.randint(2000, 8000)
                    tokens = None
                    dlp_flagged = False
                    incident_id = None
                    response_hash = None

                row = AuditLog(
                    api_key=team.api_key,
                    team_name=team.team_name,
                    model=team.model,
                    status=status,
                    prompt_hash=_fake_hash(),
                    response_hash=response_hash,
                    response_status=response_status,
                    latency_ms=latency,
                    auth_ms=random.randint(1, 6),
                    dlp_ms=random.randint(2, 18),
                    inject_ms=random.randint(1, 4),
                    vllm_ms=(latency - random.randint(20, 60)) if status == "success" else None,
                    dlp_flagged=dlp_flagged,
                    incident_id=incident_id,
                    tokens_used=tokens,
                    client_ip=random.choice(CLIENT_IPS),
                    timestamp=ts,
                )
                db.add(row)
                rows += 1

    await db.flush()
    return rows, dlp_blocks


async def _create_dlp_incidents(
    db, dlp_blocks: list[tuple[Team, str, datetime]]
) -> int:
    severities = ["Critical", "High", "Medium", "Low"]
    sev_weights = [0.25, 0.40, 0.25, 0.10]

    for team, incident_id, ts in dlp_blocks:
        # Pick 1–3 pattern hits.
        n = random.choices([1, 2, 3], weights=[0.7, 0.25, 0.05])[0]
        patterns = random.sample(DLP_PATTERN_NAMES, k=n)
        sevs = random.choices(severities, weights=sev_weights, k=n)
        # Strongest-wins.
        max_sev = sorted(sevs, key=lambda s: severities.index(s))[0]
        match_counts = {p: random.randint(1, 4) for p in patterns}

        action = "block" if max_sev in ("Critical", "High") else random.choice(["block", "redact", "alert"])

        incident = DLPIncident(
            incident_id=incident_id,
            api_key=team.api_key,
            team_name=team.team_name,
            client_ip=random.choice(CLIENT_IPS),
            patterns=patterns,
            severities=sevs,
            max_severity=max_sev,
            match_counts=match_counts,
            message_len=random.randint(80, 2400),
            source=random.choices(["user_input", "model_response"], weights=[0.85, 0.15])[0],
            action=action,
            timestamp=ts,
        )
        db.add(incident)

    await db.flush()
    return len(dlp_blocks)


async def _create_activity_log(
    db, admin: User, extra_users: list[User], teams: list[Team]
) -> int:
    actions: list[dict] = []

    for team in teams:
        actions.append({
            "user": admin,
            "action": "create_team",
            "target_type": "team",
            "target_id": str(team.id),
            "changes": {"team_name": team.team_name, "model": team.model},
            "ts": team.created_at,
        })

    for user in extra_users:
        actions.append({
            "user": admin,
            "action": "create_user",
            "target_type": "user",
            "target_id": str(user.id),
            "changes": {"username": user.username, "role": user.role},
            "ts": user.created_at,
        })

    # Some recent admin activity to make the page feel live.
    recent_targets = [(t.team_name, str(t.id)) for t in teams]
    for _ in range(8):
        name, tid = random.choice(recent_targets)
        actions.append({
            "user": admin,
            "action": random.choice([
                "update_team_rate_limit",
                "update_team_system_prompt",
                "rotate_team_api_key",
                "update_dlp_pattern",
            ]),
            "target_type": "team",
            "target_id": tid,
            "changes": {"team_name": name},
            "ts": NOW - timedelta(hours=random.randint(1, 96)),
        })

    for a in actions:
        db.add(UserActivityLog(
            user_id=a["user"].id,
            username=a["user"].username,
            action=a["action"],
            target_type=a["target_type"],
            target_id=a["target_id"],
            changes=a["changes"],
            ip_address="10.0.0.5",
            timestamp=a["ts"],
        ))

    await db.flush()
    return len(actions)


async def main() -> None:
    wipe_only = "--wipe" in sys.argv

    async with AsyncSessionLocal() as db:
        admin_result = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_result.scalars().first()
        if admin is None:
            print("ERROR: admin user not found. Has the app started and seeded yet?")
            return

        print("Wiping existing demo rows...")
        await _wipe(db)

        if wipe_only:
            await db.commit()
            print()
            print("=" * 60)
            print("Demo data wiped. Admin user, DLP patterns, and gateway")
            print("settings were preserved.")
            print("=" * 60)
            return

        print("Creating teams...")
        teams = await _create_teams(db)

        print("Creating extra users...")
        users = await _create_users(db, admin)

        print("Creating audit logs (this is the slow part)...")
        audit_count, dlp_blocks = await _create_audit_logs(db, teams)

        print("Creating DLP incidents...")
        dlp_count = await _create_dlp_incidents(db, dlp_blocks)

        print("Creating activity log entries...")
        activity_count = await _create_activity_log(db, admin, users, teams)

        await db.commit()

        print()
        print("=" * 60)
        print("Demo data seeded.")
        print(f"  teams                : {len(teams)}")
        print(f"  extra users          : {len(users)}")
        print(f"  audit_logs           : {audit_count}")
        print(f"  dlp_incidents        : {dlp_count}")
        print(f"  user_activity_log    : {activity_count}")
        print("=" * 60)
        print()
        print("Extra users (password for all): synapse")
        for u in EXTRA_USERS:
            print(f"  {u['username']:20s}  role={u['role']}")


if __name__ == "__main__":
    asyncio.run(main())
