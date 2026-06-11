"""Security controls — password age, session jti, password history table.

Revision ID: 002
Revises: 001
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dialect-agnostic + idempotent: SQLAlchemy types render per-backend
    # (Postgres/MSSQL/SQLite) and the inspector guards make this safe to run on a
    # database that was already partially created via SQLAlchemy create_all().
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── Add new columns to users ───────────────────────────────────────────────
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "password_changed_at" not in user_columns:
        op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    if "active_session_jti" not in user_columns:
        op.add_column("users", sa.Column("active_session_jti", sa.String(length=36), nullable=True))

    # ── user_password_history ──────────────────────────────────────────────────
    if "user_password_history" not in inspector.get_table_names():
        op.create_table(
            "user_password_history",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("hashed_password", sa.String(length=200), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_user_password_history_user_id", "user_password_history", ["user_id"]
        )
        op.create_index(
            "ix_user_password_history_changed_at", "user_password_history", ["changed_at"]
        )


def downgrade() -> None:
    op.drop_index("ix_user_password_history_changed_at", table_name="user_password_history")
    op.drop_index("ix_user_password_history_user_id", table_name="user_password_history")
    op.drop_table("user_password_history")
    op.drop_column("users", "active_session_jti")
    op.drop_column("users", "password_changed_at")
