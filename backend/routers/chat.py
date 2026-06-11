"""
Chat completions proxy — POST /v1/chat/completions

OpenAI-compatible endpoint. Uses Bearer API key (team api_key), NOT JWT.

Pipeline:
  1. Auth (incl. key expiry) + rate limit + daily token budget
  2. System prompt injection
  3. DLP scan on last user message (block | redact | alert)
  4. Forward to selected backend (on-prem vs cloud, per data_classification)
  5. DLP scan on response
  6. Audit log + return
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import state
from config import settings
from constants import (
    SEVERITY_ORDER,
    AuditStatus,
    DataClassification,
    DLPAction,
    DLPSource,
    Severity,
)
from database import AsyncSessionLocal

router = APIRouter()

logger = logging.getLogger(__name__)


def _elapsed_ms(start: float) -> int:
    """Milliseconds elapsed since a time.monotonic() start point."""
    return int((time.monotonic() - start) * 1000)


def _today_iso() -> str:
    return datetime.utcnow().date().isoformat()


def _seconds_to_utc_midnight() -> int:
    now = datetime.utcnow()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def _tokens_used_today(api_key: str) -> int:
    entry = state.tokens_today.get(api_key)
    if not entry or entry.get("date") != _today_iso():
        return 0
    return int(entry.get("tokens", 0))


def _add_tokens_today(api_key: str, n: int) -> None:
    today = _today_iso()
    entry = state.tokens_today.get(api_key)
    if not entry or entry.get("date") != today:
        state.tokens_today[api_key] = {"date": today, "tokens": int(n)}
    else:
        entry["tokens"] = int(entry.get("tokens", 0)) + int(n)


def _rate_limit_headers(limit: int, remaining: int, reset_seconds: int) -> dict[str, str]:
    """Standard X-RateLimit-* + Retry-After headers for a request-rate 429."""
    return {
        "Retry-After": str(max(1, reset_seconds)),
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(int(time.time()) + max(1, reset_seconds)),
    }


def _token_limit_headers(limit: int, used: int, reset_seconds: int) -> dict[str, str]:
    """Token-budget variant of the rate-limit headers."""
    return {
        "Retry-After": str(max(1, reset_seconds)),
        "X-RateLimit-Tokens-Limit": str(limit),
        "X-RateLimit-Tokens-Remaining": str(max(0, limit - used)),
        "X-RateLimit-Tokens-Reset": str(int(time.time()) + max(1, reset_seconds)),
    }


def _pick_backend_url(team_cfg: dict) -> str:
    """Hybrid routing — non-sensitive teams may go to the cloud backend.

    Sensitive (default) always routes to the on-prem vllm_url. Non-sensitive
    routes to cloud_vllm_url when one is configured, otherwise falls back to
    on-prem (safer default than failing).
    """
    on_prem = state.gateway_settings.get("vllm_url", settings.VLLM_URL).rstrip("/")
    if team_cfg.get("data_classification") == DataClassification.NON_SENSITIVE:
        cloud = state.gateway_settings.get("cloud_vllm_url", settings.CLOUD_VLLM_URL).rstrip("/")
        if cloud:
            return cloud
    return on_prem


def _apply_redactions(text: str) -> str:
    """Replace every redact-action pattern match with a marker."""
    for p in state.dlp_patterns:
        if p["enabled"] and p["compiled"] and p.get("action") == DLPAction.REDACT:
            text = p["compiled"].sub(f"[REDACTED:{p['name']}]", text)
    return text


# ---------------------------------------------------------------------------
# Persistent HTTP client — reuse TCP connections across requests
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None


async def _get_client(timeout_sec: int) -> httpx.AsyncClient:
    """Return a module-level AsyncClient, creating it if needed."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.HTTP_CONNECT_TIMEOUT_SEC,
                read=timeout_sec,
                write=settings.HTTP_WRITE_TIMEOUT_SEC,
                pool=settings.HTTP_POOL_TIMEOUT_SEC,
            ),
            limits=httpx.Limits(
                max_keepalive_connections=settings.HTTP_MAX_KEEPALIVE_CONNECTIONS,
                max_connections=settings.HTTP_MAX_CONNECTIONS,
            ),
            trust_env=False,
            follow_redirects=True,
        )
    return _http_client


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


# ---------------------------------------------------------------------------
# DLP severity helper
# ---------------------------------------------------------------------------
def _highest_severity(severities: list[str]) -> str:
    if not severities:
        return Severity.LOW
    return max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))


# ---------------------------------------------------------------------------
# Async DB write helpers (called via asyncio.create_task)
# ---------------------------------------------------------------------------
async def _write_audit_log(data: dict) -> None:
    from models import AuditLog  # noqa: PLC0415

    try:
        async with AsyncSessionLocal() as db:
            db.add(AuditLog(**data))
            await db.commit()
    except Exception:
        logger.exception("Failed to write audit log (status=%s)", data.get("status"))


async def _write_dlp_incident(data: dict) -> None:
    from models import DLPIncident  # noqa: PLC0415

    try:
        async with AsyncSessionLocal() as db:
            db.add(DLPIncident(**data))
            await db.commit()
    except Exception:
        logger.exception(
            "Failed to write DLP incident (incident_id=%s)", data.get("incident_id")
        )


def _fire_audit(
    *,
    api_key: str,
    team_name: str,
    model: str,
    status_value: str,
    client_ip: str | None,
    prompt_hash: str = "",
    response_hash: str | None = None,
    dlp_flagged: bool = False,
    incident_id: str | None = None,
    auth_ms: int | None = None,
    dlp_ms: int | None = None,
    inject_ms: int | None = None,
    vllm_ms: int | None = None,
    latency_ms: int | None = None,
    response_status: int | None = None,
    tokens_used: int | None = None,
) -> None:
    """Assemble an audit-log record and persist it detached (never blocks)."""
    data: dict[str, Any] = {
        "api_key": api_key,
        "team_name": team_name,
        "model": model,
        "status": status_value,
        "prompt_hash": prompt_hash,
        "dlp_flagged": dlp_flagged,
        "client_ip": client_ip,
        "timestamp": datetime.utcnow(),
    }
    optional = {
        "response_hash": response_hash,
        "incident_id": incident_id,
        "auth_ms": auth_ms,
        "dlp_ms": dlp_ms,
        "inject_ms": inject_ms,
        "vllm_ms": vllm_ms,
        "latency_ms": latency_ms,
        "response_status": response_status,
        "tokens_used": tokens_used,
    }
    data.update({k: v for k, v in optional.items() if v is not None})
    asyncio.create_task(_write_audit_log(data))


def _fire_dlp_incident(
    *,
    api_key: str,
    team_name: str,
    client_ip: str | None,
    dlp_result: dict,
    message_len: int,
    source: str,
    action: str,
) -> str:
    """Persist a DLP incident detached and return its generated incident_id."""
    incident_id = str(uuid.uuid4())
    asyncio.create_task(
        _write_dlp_incident(
            {
                "incident_id": incident_id,
                "api_key": api_key,
                "team_name": team_name,
                "client_ip": client_ip or "",
                "patterns": dlp_result["patterns"],
                "severities": dlp_result["severities"],
                "max_severity": dlp_result["max_severity"],
                "match_counts": dlp_result["match_counts"],
                "message_len": message_len,
                "source": source,
                "action": action,
                "timestamp": datetime.utcnow(),
            }
        )
    )
    return incident_id


# ---------------------------------------------------------------------------
# DLP scan helper
# ---------------------------------------------------------------------------
def _run_dlp(text: str) -> dict:
    """Scan text against enabled patterns; return findings + action breakdown."""
    matched_patterns: list[str] = []
    matched_severities: list[str] = []
    matched_actions: list[str] = []
    match_counts: dict[str, int] = {}
    findings: list[dict] = []

    for p in state.dlp_patterns:
        if not p["enabled"] or p["compiled"] is None:
            continue
        matches = p["compiled"].findall(text)
        if matches:
            matched_patterns.append(p["name"])
            matched_severities.append(p["severity"])
            matched_actions.append(p.get("action", DLPAction.BLOCK))
            match_counts[p["name"]] = len(matches)
            findings.append(
                {
                    "pattern": p["name"],
                    "severity": p["severity"],
                    "action": p.get("action", DLPAction.BLOCK),
                }
            )

    return {
        "flagged": bool(matched_patterns),
        "patterns": matched_patterns,
        "severities": matched_severities,
        "actions": matched_actions,
        "max_severity": _highest_severity(matched_severities),
        "match_counts": match_counts,
        "findings": findings,
    }


def _dominant_action(actions: list[str]) -> str | None:
    """Pick the strongest action present: block > redact > alert."""
    if DLPAction.BLOCK in actions:
        return DLPAction.BLOCK
    if DLPAction.REDACT in actions:
        return DLPAction.REDACT
    if DLPAction.ALERT in actions:
        return DLPAction.ALERT
    return None


# ---------------------------------------------------------------------------
# Pipeline step helpers
# ---------------------------------------------------------------------------
def _build_messages_with_system_prompt(
    body: ChatCompletionRequest, team_cfg: dict
) -> list[dict[str, str]]:
    """Strip any client-supplied system messages and prepend the key-bound one."""
    messages: list[dict[str, str]] = [
        {"role": m.role, "content": m.content}
        for m in body.messages
        if m.role != "system"
    ]
    system_prompt: str = (
        team_cfg.get("system_prompt")
        or state.gateway_settings.get("default_system_prompt", "")
    )
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    return messages


def _extract_last_user_message(messages: list[dict[str, str]]) -> str:
    """Return the content of the most recent user message, or empty string."""
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return ""


def _replace_last_user_message(messages: list[dict[str, str]], new_content: str) -> None:
    for m in reversed(messages):
        if m["role"] == "user":
            m["content"] = new_content
            return


# ---------------------------------------------------------------------------
# POST /v1/chat/completions
# ---------------------------------------------------------------------------
@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request) -> Any:
    t_total_start = time.monotonic()
    client_ip: str | None = request.client.host if request.client else None

    # ── STEP 1 — AUTH + EXPIRY + RATE LIMIT + TOKEN BUDGET ──────────────────
    t_auth_start = time.monotonic()

    auth_header: str | None = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # No credential supplied at all — 401 is the conventional response.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    api_key = auth_header[len("Bearer "):].strip()

    team_cfg = state.rate_limit_config.get(api_key)
    if team_cfg is None or not team_cfg["enabled"]:
        _fire_audit(
            api_key=api_key,
            team_name=team_cfg["team_name"] if team_cfg else "unknown",
            model=body.model or "",
            status_value=AuditStatus.BLOCKED_AUTH,
            client_ip=client_ip,
            auth_ms=_elapsed_ms(t_auth_start),
            response_status=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or disabled API key",
        )

    # API key expiry (NULL expires_at = never expires).
    expires_at = team_cfg.get("expires_at")
    if expires_at is not None and expires_at <= datetime.utcnow():
        _fire_audit(
            api_key=api_key,
            team_name=team_cfg["team_name"],
            model=body.model or team_cfg["model"],
            status_value=AuditStatus.BLOCKED_AUTH,
            client_ip=client_ip,
            auth_ms=_elapsed_ms(t_auth_start),
            response_status=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has expired",
        )

    team_name: str = team_cfg["team_name"]
    limit: int = team_cfg["requests"]
    window_sec: int = team_cfg["window_sec"]
    tokens_per_day = team_cfg.get("tokens_per_day")

    now_ts = time.time()
    state.request_log[api_key] = [
        ts for ts in state.request_log[api_key] if now_ts - ts < window_sec
    ]
    current_count = len(state.request_log[api_key])
    auth_ms = _elapsed_ms(t_auth_start)

    if current_count >= limit:
        oldest = min(state.request_log[api_key]) if state.request_log[api_key] else now_ts
        retry_after = int(window_sec - (now_ts - oldest)) + 1
        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=body.model or team_cfg["model"],
            status_value=AuditStatus.BLOCKED_RATE_LIMIT,
            client_ip=client_ip,
            auth_ms=auth_ms,
            response_status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "team": team_name,
                "limit": limit,
                "window_sec": window_sec,
                "retry_after": retry_after,
            },
            headers=_rate_limit_headers(limit, 0, retry_after),
        )

    # Daily token budget (NULL = unlimited). Enforced lazily: if we are already
    # over the budget from earlier requests, reject; otherwise allow this one to
    # run and add its tokens after success.
    if tokens_per_day is not None:
        used_today = _tokens_used_today(api_key)
        if used_today >= tokens_per_day:
            reset = _seconds_to_utc_midnight()
            _fire_audit(
                api_key=api_key,
                team_name=team_name,
                model=body.model or team_cfg["model"],
                status_value=AuditStatus.BLOCKED_RATE_LIMIT,
                client_ip=client_ip,
                auth_ms=auth_ms,
                response_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Daily token budget exhausted",
                    "team": team_name,
                    "tokens_per_day": tokens_per_day,
                    "tokens_used_today": used_today,
                    "retry_after": reset,
                },
                headers=_token_limit_headers(tokens_per_day, used_today, reset),
            )

    # Record this request against the per-window counter.
    state.request_log[api_key].append(now_ts)

    # ── STEP 2 — SYSTEM PROMPT INJECTION ────────────────────────────────────
    t_inject_start = time.monotonic()
    messages = _build_messages_with_system_prompt(body, team_cfg)
    inject_ms = _elapsed_ms(t_inject_start)

    # ── STEP 3 — DLP SCAN REQUEST ───────────────────────────────────────────
    t_dlp_start = time.monotonic()
    last_user_msg = _extract_last_user_message(messages)
    # Hash is always of the ORIGINAL prompt — preserves forensic matching even
    # when the forwarded payload is redacted.
    prompt_hash = hashlib.sha256(last_user_msg.encode()).hexdigest() if last_user_msg else ""
    dlp_result = _run_dlp(last_user_msg)
    dlp_ms = _elapsed_ms(t_dlp_start)
    dlp_incident_id: str | None = None

    if dlp_result["flagged"]:
        action = _dominant_action(dlp_result["actions"]) or DLPAction.BLOCK

        if action == DLPAction.BLOCK:
            incident_id = _fire_dlp_incident(
                api_key=api_key,
                team_name=team_name,
                client_ip=client_ip,
                dlp_result=dlp_result,
                message_len=len(last_user_msg),
                source=DLPSource.USER_INPUT,
                action=DLPAction.BLOCK,
            )
            _fire_audit(
                api_key=api_key,
                team_name=team_name,
                model=body.model or team_cfg["model"],
                status_value=AuditStatus.BLOCKED_DLP,
                client_ip=client_ip,
                prompt_hash=prompt_hash,
                dlp_flagged=True,
                incident_id=incident_id,
                auth_ms=auth_ms,
                dlp_ms=dlp_ms,
                inject_ms=inject_ms,
                latency_ms=_elapsed_ms(t_total_start),
                response_status=status.HTTP_400_BAD_REQUEST,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Request blocked by DLP policy",
                    "incident_id": incident_id,
                    "findings": dlp_result["findings"],
                },
            )

        # REDACT: substitute matches and continue.
        if action == DLPAction.REDACT:
            redacted = _apply_redactions(last_user_msg)
            _replace_last_user_message(messages, redacted)
            last_user_msg = redacted
            dlp_incident_id = _fire_dlp_incident(
                api_key=api_key,
                team_name=team_name,
                client_ip=client_ip,
                dlp_result=dlp_result,
                message_len=len(redacted),
                source=DLPSource.USER_INPUT,
                action=DLPAction.REDACT,
            )

        # ALERT: log incident, forward unchanged.
        elif action == DLPAction.ALERT:
            dlp_incident_id = _fire_dlp_incident(
                api_key=api_key,
                team_name=team_name,
                client_ip=client_ip,
                dlp_result=dlp_result,
                message_len=len(last_user_msg),
                source=DLPSource.USER_INPUT,
                action=DLPAction.ALERT,
            )

    # ── STEP 4 — FORWARD TO LLM BACKEND (hybrid routing) ────────────────────
    t_vllm_start = time.monotonic()
    vllm_url = _pick_backend_url(team_cfg)
    timeout_sec = int(state.gateway_settings.get("timeout_sec", settings.LLM_REQUEST_TIMEOUT_SEC))
    assigned_model: str = team_cfg["model"]

    if body.model and body.model != assigned_model:
        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=body.model,
            status_value=AuditStatus.BLOCKED_AUTH,
            client_ip=client_ip,
            auth_ms=auth_ms,
            response_status=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Model '{body.model}' is not authorized for this API key. Assigned model: '{assigned_model}'.",
        )

    target_model = assigned_model
    vllm_payload: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "temperature": body.temperature,
        "stream": body.stream or False,
    }
    if body.max_tokens is not None:
        vllm_payload["max_tokens"] = body.max_tokens

    if body.stream:
        return await _handle_streaming(
            vllm_url=vllm_url,
            vllm_payload=vllm_payload,
            timeout_sec=timeout_sec,
            api_key=api_key,
            team_name=team_name,
            target_model=target_model,
            prompt_hash=prompt_hash,
            client_ip=client_ip,
            auth_ms=auth_ms,
            dlp_ms=dlp_ms,
            inject_ms=inject_ms,
            dlp_incident_id=dlp_incident_id,
            dlp_flagged=dlp_result["flagged"],
            t_total_start=t_total_start,
            t_vllm_start=t_vllm_start,
        )

    try:
        client = await _get_client(timeout_sec)
        vllm_response = await client.post(
            f"{vllm_url}/chat/completions",
            json=vllm_payload,
        )
    except httpx.TimeoutException:
        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=target_model,
            status_value=AuditStatus.ERROR,
            client_ip=client_ip,
            prompt_hash=prompt_hash,
            auth_ms=auth_ms,
            dlp_ms=dlp_ms,
            inject_ms=inject_ms,
            latency_ms=_elapsed_ms(t_total_start),
            response_status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="vLLM request timed out",
        )
    except httpx.ConnectError:
        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=target_model,
            status_value=AuditStatus.ERROR,
            client_ip=client_ip,
            prompt_hash=prompt_hash,
            auth_ms=auth_ms,
            dlp_ms=dlp_ms,
            inject_ms=inject_ms,
            latency_ms=_elapsed_ms(t_total_start),
            response_status=status.HTTP_502_BAD_GATEWAY,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot connect to vLLM backend",
        )

    vllm_ms = _elapsed_ms(t_vllm_start)

    if not (200 <= vllm_response.status_code < 300):
        try:
            err_body = vllm_response.json()
            err_detail = err_body.get("error") or err_body.get("detail") or str(err_body)
        except Exception:
            err_detail = vllm_response.text[:500] or f"HTTP {vllm_response.status_code}"

        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=target_model,
            status_value=AuditStatus.ERROR,
            client_ip=client_ip,
            prompt_hash=prompt_hash,
            auth_ms=auth_ms,
            dlp_ms=dlp_ms,
            inject_ms=inject_ms,
            vllm_ms=vllm_ms,
            latency_ms=_elapsed_ms(t_total_start),
            response_status=vllm_response.status_code,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_detail)

    # ── STEP 5 — DLP SCAN RESPONSE ──────────────────────────────────────────
    t_dlp_resp_start = time.monotonic()

    try:
        vllm_data = vllm_response.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid JSON from vLLM backend",
        )

    response_text = ""
    try:
        response_text = vllm_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass

    dlp_resp_result = _run_dlp(response_text)
    dlp_resp_ms = _elapsed_ms(t_dlp_resp_start)

    if dlp_resp_result["flagged"]:
        # Response-side DLP only blocks (redaction of streamed/already-generated
        # content is out of scope; alert on response is a future addition).
        incident_id = _fire_dlp_incident(
            api_key=api_key,
            team_name=team_name,
            client_ip=client_ip,
            dlp_result=dlp_resp_result,
            message_len=len(response_text),
            source=DLPSource.MODEL_RESPONSE,
            action=DLPAction.BLOCK,
        )
        _fire_audit(
            api_key=api_key,
            team_name=team_name,
            model=target_model,
            status_value=AuditStatus.BLOCKED_DLP,
            client_ip=client_ip,
            prompt_hash=prompt_hash,
            dlp_flagged=True,
            incident_id=incident_id,
            auth_ms=auth_ms,
            dlp_ms=dlp_ms + dlp_resp_ms,
            inject_ms=inject_ms,
            vllm_ms=vllm_ms,
            latency_ms=_elapsed_ms(t_total_start),
            response_status=vllm_response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Response blocked by DLP policy",
                "incident_id": incident_id,
                "findings": dlp_resp_result["findings"],
            },
        )

    # ── STEP 6 — AUDIT LOG + RETURN ─────────────────────────────────────────
    tokens_used: int | None = None
    try:
        tokens_used = vllm_data.get("usage", {}).get("total_tokens")
    except AttributeError:
        pass

    response_hash = hashlib.sha256(response_text.encode()).hexdigest() if response_text else None

    if tokens_used:
        _add_tokens_today(api_key, tokens_used)

    _fire_audit(
        api_key=api_key,
        team_name=team_name,
        model=target_model,
        status_value=AuditStatus.SUCCESS,
        client_ip=client_ip,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        dlp_flagged=dlp_result["flagged"],
        incident_id=dlp_incident_id,
        auth_ms=auth_ms,
        dlp_ms=dlp_ms + dlp_resp_ms,
        inject_ms=inject_ms,
        vllm_ms=vllm_ms,
        latency_ms=_elapsed_ms(t_total_start),
        response_status=vllm_response.status_code,
        tokens_used=tokens_used,
    )

    return vllm_data


# ---------------------------------------------------------------------------
# Streaming handler
# ---------------------------------------------------------------------------
async def _handle_streaming(
    vllm_url: str,
    vllm_payload: dict,
    timeout_sec: int,
    api_key: str,
    team_name: str,
    target_model: str,
    prompt_hash: str,
    client_ip: str | None,
    auth_ms: int,
    dlp_ms: int,
    inject_ms: int,
    dlp_incident_id: str | None,
    dlp_flagged: bool,
    t_total_start: float,
    t_vllm_start: float,
) -> StreamingResponse:
    async def event_generator():
        try:
            client = await _get_client(timeout_sec)
            async with client.stream(
                    "POST",
                    f"{vllm_url}/chat/completions",
                    json=vllm_payload,
            ) as resp:
                vllm_ms = _elapsed_ms(t_vllm_start)

                if not (200 <= resp.status_code < 300):
                    error_body = b""
                    async for chunk in resp.aiter_bytes():
                        error_body += chunk
                    try:
                        err_detail = json.loads(error_body).get("error") or error_body.decode()[:500]
                    except Exception:
                        err_detail = error_body.decode(errors="replace")[:500] or f"HTTP {resp.status_code}"

                    yield (
                        f"data: {json.dumps({'error': err_detail, 'status': resp.status_code})}\n\n"
                        "data: [DONE]\n\n"
                    ).encode()

                    _fire_audit(
                        api_key=api_key,
                        team_name=team_name,
                        model=target_model,
                        status_value=AuditStatus.ERROR,
                        client_ip=client_ip,
                        prompt_hash=prompt_hash,
                        dlp_flagged=dlp_flagged,
                        incident_id=dlp_incident_id,
                        auth_ms=auth_ms,
                        dlp_ms=dlp_ms,
                        inject_ms=inject_ms,
                        vllm_ms=vllm_ms,
                        latency_ms=_elapsed_ms(t_total_start),
                        response_status=resp.status_code,
                    )
                    return

                async for chunk in resp.aiter_bytes():
                    yield chunk

            _fire_audit(
                api_key=api_key,
                team_name=team_name,
                model=target_model,
                status_value=AuditStatus.SUCCESS,
                client_ip=client_ip,
                prompt_hash=prompt_hash,
                dlp_flagged=dlp_flagged,
                incident_id=dlp_incident_id,
                auth_ms=auth_ms,
                dlp_ms=dlp_ms,
                inject_ms=inject_ms,
                vllm_ms=vllm_ms,
                latency_ms=_elapsed_ms(t_total_start),
                response_status=status.HTTP_200_OK,
            )
        except httpx.TimeoutException:
            _fire_audit(
                api_key=api_key,
                team_name=team_name,
                model=target_model,
                status_value=AuditStatus.ERROR,
                client_ip=client_ip,
                prompt_hash=prompt_hash,
                latency_ms=_elapsed_ms(t_total_start),
                response_status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except httpx.ConnectError:
            _fire_audit(
                api_key=api_key,
                team_name=team_name,
                model=target_model,
                status_value=AuditStatus.ERROR,
                client_ip=client_ip,
                prompt_hash=prompt_hash,
                latency_ms=_elapsed_ms(t_total_start),
                response_status=status.HTTP_502_BAD_GATEWAY,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
