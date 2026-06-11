"""Shared helpers for masking sensitive values in API responses and exports."""
from __future__ import annotations

_API_KEY_VISIBLE_SUFFIX = 8


def mask_api_key(key: str | None) -> str:
    """Return the key with all but the last 8 characters replaced by asterisks.

    Short keys (<= 8 chars) are returned unchanged. Used everywhere an api_key
    is surfaced to a non-admin context so the full credential is never exposed.
    """
    if not key:
        return ""
    if len(key) <= _API_KEY_VISIBLE_SUFFIX:
        return key
    return "*" * (len(key) - _API_KEY_VISIBLE_SUFFIX) + key[-_API_KEY_VISIBLE_SUFFIX:]


def mask_ip(ip: str | None) -> str:
    """Replace the last octet of an IPv4 address with 'xxx' for privacy.

    Non-IPv4 values are returned unchanged; None/empty returns an empty string.
    """
    if not ip:
        return ""
    parts = ip.split(".")
    if len(parts) == 4:
        parts[-1] = "xxx"
        return ".".join(parts)
    return ip
