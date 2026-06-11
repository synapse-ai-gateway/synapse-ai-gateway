"""Initial schema — all 7 tables.

Revision ID: 001
Revises:
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="readonly"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── teams ──────────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(36), nullable=False),
        sa.Column("team_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False, server_default=""),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("window_sec", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teams_api_key", "teams", ["api_key"], unique=True)

    # ── dlp_incidents ──────────────────────────────────────────────────────────
    op.create_table(
        "dlp_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("api_key", sa.String(36), nullable=False),
        sa.Column("team_name", sa.String(100), nullable=False),
        sa.Column("client_ip", sa.String(45), nullable=False, server_default=""),
        sa.Column("patterns", sa.JSON(), nullable=False),
        sa.Column("severities", sa.JSON(), nullable=False),
        sa.Column("max_severity", sa.String(20), nullable=False, server_default=""),
        sa.Column("match_counts", sa.JSON(), nullable=False),
        sa.Column("message_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(20), nullable=False, server_default="user_input"),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dlp_incidents_incident_id", "dlp_incidents", ["incident_id"], unique=True)
    op.create_index("ix_dlp_incidents_api_key", "dlp_incidents", ["api_key"])
    op.create_index("ix_dlp_incidents_timestamp", "dlp_incidents", ["timestamp"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(36), nullable=False),
        sa.Column("team_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="success"),
        sa.Column("prompt_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("auth_ms", sa.Integer(), nullable=True),
        sa.Column("dlp_ms", sa.Integer(), nullable=True),
        sa.Column("inject_ms", sa.Integer(), nullable=True),
        sa.Column("vllm_ms", sa.Integer(), nullable=True),
        sa.Column("dlp_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("incident_id", sa.String(36), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_api_key", "audit_logs", ["api_key"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    # ── dlp_patterns ───────────────────────────────────────────────────────────
    op.create_table(
        "dlp_patterns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dlp_patterns_name", "dlp_patterns", ["name"], unique=True)

    # ── gateway_settings ───────────────────────────────────────────────────────
    op.create_table(
        "gateway_settings",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )

    # ── user_activity_log ──────────────────────────────────────────────────────
    op.create_table(
        "user_activity_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("target_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activity_log_timestamp", "user_activity_log", ["timestamp"])


def downgrade() -> None:
    op.drop_table("user_activity_log")
    op.drop_table("gateway_settings")
    op.drop_table("dlp_patterns")
    op.drop_table("audit_logs")
    op.drop_table("dlp_incidents")
    op.drop_table("teams")
    op.drop_table("users")
