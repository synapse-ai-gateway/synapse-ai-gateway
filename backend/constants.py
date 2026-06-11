"""Shared constant string values used across the gateway.

Centralises the audit-log status values, DLP incident sources, and DLP severity
levels so they are defined once rather than repeated as string literals.
Plain string constants (not Enum) are used so values pass through SQLAlchemy and
JSON exactly as before.
"""
from __future__ import annotations


class AuditStatus:
    """Allowed values for AuditLog.status."""

    SUCCESS = "success"
    BLOCKED_AUTH = "blocked_auth"
    BLOCKED_DLP = "blocked_dlp"
    BLOCKED_RATE_LIMIT = "blocked_rate_limit"
    ERROR = "error"


class DLPSource:
    """Allowed values for DLPIncident.source."""

    USER_INPUT = "user_input"
    MODEL_RESPONSE = "model_response"


class Severity:
    """Allowed DLP severity levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Ranking used to pick the highest severity among several matches.
SEVERITY_ORDER: dict[str, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}

# The set of valid severity strings, for input validation.
SEVERITY_VALUES: frozenset[str] = frozenset(SEVERITY_ORDER)


class DLPAction:
    """Per-pattern outcome when a DLP rule matches.

    BLOCK   — reject the request (HTTP 400, current default).
    REDACT  — substitute matches with [REDACTED:<name>] and forward the request.
    ALERT   — log an incident and forward the request unchanged.

    If a request matches several patterns with different actions, BLOCK wins,
    then REDACT, then ALERT.
    """

    BLOCK = "block"
    REDACT = "redact"
    ALERT = "alert"


DLP_ACTION_VALUES: frozenset[str] = frozenset({DLPAction.BLOCK, DLPAction.REDACT, DLPAction.ALERT})


class DataClassification:
    """Per-team data classification that drives hybrid routing.

    SENSITIVE     — must route to the on-premises LLM backend (vllm_url).
    NON_SENSITIVE — may route to the cloud backend (cloud_vllm_url) when one is
                    configured; otherwise falls back to on-prem.
    """

    SENSITIVE = "sensitive"
    NON_SENSITIVE = "non_sensitive"


CLASSIFICATION_VALUES: frozenset[str] = frozenset(
    {DataClassification.SENSITIVE, DataClassification.NON_SENSITIVE}
)
