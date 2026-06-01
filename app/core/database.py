"""
app/core/database.py
─────────────────────
Async SQLAlchemy engine + session factory for BlockShield.

Supports:
  • PostgreSQL (production)  via asyncpg
  • SQLite    (local dev)    via aiosqlite  — auto-detected from DATABASE_URL

FastAPI dependency:
    async def route(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./blockshield.db",  # dev fallback
)

# SQLite doesn't support connection pools; PostgreSQL does
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    future=True,
    poolclass=NullPool if _is_sqlite else AsyncAdaptedQueuePool,
    **({} if _is_sqlite else {
        "pool_size":     int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow":  int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_pre_ping": True,
        "pool_recycle":  1800,
    }),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a DB session and always closes it.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables (dev only — use Alembic in production)."""
    from app.models import Base  # local import avoids circular deps at module load
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables (test teardown only)."""
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
