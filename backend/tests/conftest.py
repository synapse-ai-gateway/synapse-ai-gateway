"""
Shared pytest fixtures for the Synapse AI Gateway test suite.

Strategy
--------
* A throwaway file-backed SQLite database is used in place of PostgreSQL. The
  DATABASE_URL env var is set *before* the app modules import, so the app's
  engine/session bind to the test DB.
* The vLLM/LLM backend is mocked at the `routers.chat._get_client` boundary so
  no real HTTP is made.
* Audit/DLP records are written from detached `asyncio.create_task` calls; the
  `flush_background` fixture drains those tasks so assertions are deterministic.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable

# ── Environment must be set BEFORE importing any app module ─────────────────
_TMP_DIR = tempfile.mkdtemp(prefix="synapse_test_")
_DB_PATH = Path(_TMP_DIR) / "test.db"
_BACKEND_DIR = Path(__file__).resolve().parent.parent

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only-not-real-0123456789"
os.environ["ADMIN_PASSWORD"] = "TestAdminPassword_123!"
os.environ["DLP_PATTERNS_FILE"] = str(_BACKEND_DIR / "dlp_patterns.json")
os.environ["CORS_ORIGIN"] = "http://localhost:5173"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import main  # noqa: E402  (FastAPI app)
import state  # noqa: E402
from auth import create_access_token, hash_password  # noqa: E402
from database import AsyncSessionLocal, Base, engine  # noqa: E402
from state import reload_memory  # noqa: E402

# Default API key used by most tests.
TEST_API_KEY = "test-key-0123456789abcdef"
TEST_MODEL = "test-model"


# ---------------------------------------------------------------------------
# Schema lifecycle
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    import models  # noqa: F401  ensure metadata is populated

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _isolate():
    """Reset DB rows and in-memory state before every test."""
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    state.rate_limit_config.clear()
    state.request_log.clear()
    state.dlp_patterns.clear()
    state.gateway_settings.clear()
    state.tokens_today.clear()
    yield


# ---------------------------------------------------------------------------
# Background-task draining (audit / DLP writes are fire-and-forget)
# ---------------------------------------------------------------------------
class _AsyncioShim:
    """Wraps asyncio so create_task() calls in routers.chat are recorded."""

    def __init__(self, real):
        self._real = real
        self.tasks: list = []

    def create_task(self, coro):
        task = self._real.create_task(coro)
        self.tasks.append(task)
        return task

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def flush_background(monkeypatch) -> Callable:
    """Return an async callable that awaits all detached writes made so far."""
    import asyncio as _asyncio

    import routers.chat as chat_module

    shim = _AsyncioShim(_asyncio)
    monkeypatch.setattr(chat_module, "asyncio", shim)

    async def _flush() -> None:
        if shim.tasks:
            await _asyncio.gather(*shim.tasks, return_exceptions=True)
            shim.tasks.clear()

    return _flush


# ---------------------------------------------------------------------------
# Mocked LLM backend
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else _default_completion()
        self.text = json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


def _default_completion(content: str = "Hello, I am a test assistant.") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": TEST_MODEL,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class FakeStreamResponse:
    def __init__(self, status_code: int = 200, chunks: list[bytes] | None = None):
        self.status_code = status_code
        self._chunks = chunks if chunks is not None else [
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _StreamCtx:
    def __init__(self, resp: FakeStreamResponse, exc: Exception | None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self) -> FakeStreamResponse:
        if self._exc is not None:
            raise self._exc
        return self._resp

    async def __aexit__(self, *exc_info) -> bool:
        return False


class FakeLLMClient:
    """Stand-in for the shared httpx.AsyncClient used to reach the LLM backend."""

    def __init__(self):
        self.response = FakeResponse()
        self.stream_response = FakeStreamResponse()
        self.exc: Exception | None = None  # set to make calls raise
        self.calls: list[dict] = []

    async def post(self, url: str, json: dict | None = None, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        if self.exc is not None:
            raise self.exc
        return self.response

    def stream(self, method: str, url: str, json: dict | None = None, **kwargs) -> _StreamCtx:
        self.calls.append({"url": url, "json": json, "stream": True})
        return _StreamCtx(self.stream_response, self.exc)


@pytest.fixture
def mock_llm(monkeypatch) -> FakeLLMClient:
    """Patch routers.chat._get_client so no real HTTP call is made."""
    import routers.chat as chat_module

    fake = FakeLLMClient()

    async def _fake_get_client(timeout_sec: int):
        return fake

    monkeypatch.setattr(chat_module, "_get_client", _fake_get_client)
    return fake


# ---------------------------------------------------------------------------
# HTTP client against the ASGI app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Gateway state helper — insert teams/patterns/settings and reload memory
# ---------------------------------------------------------------------------
class GatewayHelper:
    def __init__(self, db):
        self.db = db

    async def add_team(
        self,
        *,
        api_key: str = TEST_API_KEY,
        team_name: str = "Test Team",
        model: str = TEST_MODEL,
        requests: int = 100,
        window_sec: int = 60,
        enabled: bool = True,
        system_prompt: str | None = None,
        expires_at=None,
        tokens_per_day: int | None = None,
        data_classification: str = "sensitive",
    ):
        from models import Team

        self.db.add(
            Team(
                api_key=api_key,
                team_name=team_name,
                model=model,
                requests=requests,
                window_sec=window_sec,
                enabled=enabled,
                system_prompt=system_prompt,
                expires_at=expires_at,
                tokens_per_day=tokens_per_day,
                data_classification=data_classification,
            )
        )
        await self.db.commit()
        await reload_memory(self.db)

    async def add_dlp_pattern(
        self,
        *,
        name: str,
        pattern: str,
        severity: str = "Medium",
        action: str = "block",
    ):
        from models import DLPPattern

        self.db.add(
            DLPPattern(name=name, pattern=pattern, severity=severity, action=action, enabled=True)
        )
        await self.db.commit()
        await reload_memory(self.db)

    async def add_default_dlp_patterns(self):
        from models import DLPPattern

        patterns = json.loads(
            (_BACKEND_DIR / "dlp_patterns.json").read_text(encoding="utf-8")
        )
        for p in patterns:
            self.db.add(
                DLPPattern(name=p["name"], pattern=p["pattern"], severity=p["severity"], enabled=True)
            )
        await self.db.commit()
        await reload_memory(self.db)

    async def set_setting(self, key: str, value: str):
        from models import GatewaySetting

        self.db.add(GatewaySetting(key=key, value=value))
        await self.db.commit()
        await reload_memory(self.db)


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def gateway(db) -> GatewayHelper:
    return GatewayHelper(db)


# ---------------------------------------------------------------------------
# Admin user + JWT helpers (admin auth uses JWT, which *does* expire)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def admin_user(db):
    from datetime import datetime

    from models import User

    now = datetime.utcnow()
    user = User(
        username="admin",
        email="admin@yourorg.com",
        full_name="Test Admin",
        hashed_password=hash_password("TestAdminPassword_123!"),
        role="superadmin",
        enabled=True,
        force_password_change=False,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user) -> dict:
    token, jti = create_access_token(
        data={"sub": str(admin_user.id), "role": admin_user.role, "username": admin_user.username}
    )
    # Persist jti so single-session enforcement accepts the token.
    async with AsyncSessionLocal() as session:
        from models import User

        u = await session.get(User, admin_user.id)
        u.active_session_jti = jti
        await session.commit()
    return {"Authorization": f"Bearer {token}"}


def auth_header(api_key: str = TEST_API_KEY) -> dict:
    return {"Authorization": f"Bearer {api_key}"}
