"""
SQLAlchemy 2.0 ORM models.

Uses only generic SQLAlchemy column types so the schema is portable across
PostgreSQL and MSSQL without any dialect-specific imports.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# 1. users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="readonly"
    )  # superadmin | admin | analyst | readonly
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # §3.1 password age controls
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # §6.4 single session — stores the jti of the only valid JWT
    active_session_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    activity_logs: Mapped[list["UserActivityLog"]] = relationship(
        "UserActivityLog", back_populates="user", foreign_keys="[UserActivityLog.user_id]"
    )


# ---------------------------------------------------------------------------
# 2. teams
# ---------------------------------------------------------------------------
class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    api_key: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    team_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    requests: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    window_sec: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional key expiry — NULL = never expires.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Optional per-day token budget — NULL = unlimited.
    tokens_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hybrid-routing classification: sensitive (on-prem) | non_sensitive (cloud).
    data_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sensitive", server_default="sensitive"
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 3. dlp_incidents
# ---------------------------------------------------------------------------
class DLPIncident(Base):
    __tablename__ = "dlp_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incident_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    api_key: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    team_name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False, default="")
    patterns: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    severities: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    max_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    match_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    message_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user_input"
    )  # user_input | model_response
    # Outcome taken: block | redact | alert
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="block", server_default="block"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )


# ---------------------------------------------------------------------------
# 4. audit_logs
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    api_key: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    team_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="success"
    )  # success|blocked_dlp|blocked_rate_limit|blocked_auth|error
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # SHA-256 of the assistant response content (non-streaming only). NULL for
    # streaming responses since the content is forwarded chunk-by-chunk.
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auth_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dlp_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inject_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vllm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dlp_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )


# ---------------------------------------------------------------------------
# 5. dlp_patterns
# ---------------------------------------------------------------------------
class DLPPattern(Base):
    __tablename__ = "dlp_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Medium"
    )  # Critical | High | Medium | Low
    # Outcome on match: block (default) | redact | alert
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="block", server_default="block"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 6. gateway_settings
# ---------------------------------------------------------------------------
class GatewaySetting(Base):
    __tablename__ = "gateway_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# 7. user_activity_log
# ---------------------------------------------------------------------------
class UserActivityLog(Base):
    __tablename__ = "user_activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="activity_logs", foreign_keys=[user_id]
    )


# ---------------------------------------------------------------------------
# 8. user_password_history  (§3.1 — prevent reuse of last N passwords)
# ---------------------------------------------------------------------------
class UserPasswordHistory(Base):
    __tablename__ = "user_password_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
