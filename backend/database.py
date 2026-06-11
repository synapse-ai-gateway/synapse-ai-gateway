"""
Async database engine and session factory.

Supports both PostgreSQL (asyncpg) and MSSQL (aioodbc) via DATABASE_URL.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

DATABASE_URL: str = settings.DATABASE_URL

# ------------------------------------------------------------------
# Engine creation — works for asyncpg and aioodbc drivers
# ------------------------------------------------------------------
_connect_args: dict = {}

if "asyncpg" in DATABASE_URL:
    # asyncpg is already async-native; no extra args needed
    _connect_args = {}
elif "aioodbc" in DATABASE_URL:
    # aioodbc needs autocommit off handled by SQLAlchemy
    _connect_args = {}

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    connect_args=_connect_args,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ------------------------------------------------------------------
# Declarative base shared across models
# ------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------
# FastAPI dependency
# ------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and ensure it is closed after use."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
