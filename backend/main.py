"""
Synapse AI Gateway — FastAPI application entry point.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before anything else so config picks up the values
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config import settings
from database import AsyncSessionLocal, Base, engine

# Configure root logging level from LOG_LEVEL (logs go to stdout/stderr —
# container-friendly; no log files are written by the application).
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan: create tables → seed → reload memory
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Import models so Base.metadata is populated before create_all
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        from seed import seed_database

        await seed_database(db)

    async with AsyncSessionLocal() as db:
        from state import reload_memory

        await reload_memory(db)

    yield
    # Teardown (if needed in the future)
    await engine.dispose()


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Synapse AI Gateway",
    version="1.0.0",
    description="Secure, audited AI proxy gateway for YourOrg internal teams.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# §6.3 Cache-Control: no-store for all API responses
# ---------------------------------------------------------------------------
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(NoCacheMiddleware)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from routers.admin_audit import router as admin_audit_router
from routers.admin_dlp import router as admin_dlp_router
from routers.admin_incidents import router as admin_incidents_router
from routers.admin_models import router as admin_models_router
from routers.admin_settings import router as admin_settings_router
from routers.admin_stats import router as admin_stats_router
from routers.admin_teams import router as admin_teams_router
from routers.admin_users import router as admin_users_router
from routers.auth import router as auth_router
from routers.chat import router as chat_router

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(admin_teams_router, prefix="/admin", tags=["Admin: Teams"])
app.include_router(admin_incidents_router, prefix="/admin", tags=["Admin: Incidents"])
app.include_router(admin_audit_router, prefix="/admin", tags=["Admin: Audit"])
app.include_router(admin_stats_router, prefix="/admin", tags=["Admin: Stats"])
app.include_router(admin_dlp_router, prefix="/admin", tags=["Admin: DLP"])
app.include_router(admin_settings_router, prefix="/admin", tags=["Admin: Settings"])
app.include_router(admin_users_router, prefix="/admin", tags=["Admin: Users"])
app.include_router(admin_models_router, prefix="/admin", tags=["Admin: Models"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "Synapse AI Gateway"}
