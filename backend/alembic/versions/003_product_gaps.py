"""Product-gap columns: key expiry, token budget, classification, DLP action, response hash.

Revision ID: 003
Revises: 002
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── teams: expires_at, tokens_per_day, data_classification ──────────────
    team_cols = {c["name"] for c in inspector.get_columns("teams")}
    if "expires_at" not in team_cols:
        op.add_column("teams", sa.Column("expires_at", sa.DateTime(), nullable=True))
    if "tokens_per_day" not in team_cols:
        op.add_column("teams", sa.Column("tokens_per_day", sa.Integer(), nullable=True))
    if "data_classification" not in team_cols:
        op.add_column(
            "teams",
            sa.Column(
                "data_classification",
                sa.String(length=20),
                nullable=False,
                server_default="sensitive",
            ),
        )

    # ── dlp_patterns: action ────────────────────────────────────────────────
    pat_cols = {c["name"] for c in inspector.get_columns("dlp_patterns")}
    if "action" not in pat_cols:
        op.add_column(
            "dlp_patterns",
            sa.Column(
                "action",
                sa.String(length=20),
                nullable=False,
                server_default="block",
            ),
        )

    # ── dlp_incidents: action ───────────────────────────────────────────────
    inc_cols = {c["name"] for c in inspector.get_columns("dlp_incidents")}
    if "action" not in inc_cols:
        op.add_column(
            "dlp_incidents",
            sa.Column(
                "action",
                sa.String(length=20),
                nullable=False,
                server_default="block",
            ),
        )

    # ── audit_logs: response_hash ───────────────────────────────────────────
    audit_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
    if "response_hash" not in audit_cols:
        op.add_column(
            "audit_logs",
            sa.Column("response_hash", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("audit_logs", "response_hash")
    op.drop_column("dlp_incidents", "action")
    op.drop_column("dlp_patterns", "action")
    op.drop_column("teams", "data_classification")
    op.drop_column("teams", "tokens_per_day")
    op.drop_column("teams", "expires_at")
