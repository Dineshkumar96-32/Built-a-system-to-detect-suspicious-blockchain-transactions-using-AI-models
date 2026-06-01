"""
tests/conftest.py
─────────────────
Root pytest configuration for BlockShield.

THE CRITICAL FIX
================
SQLite's `sqlite+aiosqlite:///:memory:` creates a *new, empty* database for
every connection. When tests use separate fixtures that each open their own
connection, the second connection sees no tables.

Solution: create ONE shared engine (scope="session"), create all tables once,
and share that engine with every test via a module-scoped `db` fixture that
rolls back between tests using SAVEPOINT / nested transactions.

This file is discovered automatically by pytest because it lives in `tests/`.

Environment
-----------
All env-vars are set to safe test defaults BEFORE any app module is imported,
so no accidental reads from a real .env file can break the suite.
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# ── Force test environment BEFORE any app import ──────────────
os.environ.setdefault("DATABASE_URL",    "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret-32-characters-xxxxx!")
os.environ.setdefault("BROKER_BACKEND",  "memory")
os.environ.setdefault("LOG_JSON",        "false")
os.environ.setdefault("LOG_LEVEL",       "WARNING")
os.environ.setdefault("MODEL_DIR",       "/tmp/blockshield_test_models")
os.environ.setdefault("REDIS_ENABLED",   "false")
os.environ.setdefault("API_KEYS",        "test-api-key")


# ─────────────────────────────────────────────────────────────
# Event loop — one loop for the entire session
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """
    Single asyncio event loop shared across the entire test session.
    Required when session-scoped async fixtures are used.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─────────────────────────────────────────────────────────────
# Shared SQLite engine — created ONCE, tables created ONCE
# ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """
    Single async engine for the whole test session.

    SQLite :memory: with `check_same_thread=False` + StaticPool so every
    connection sees the same in-memory database.
    StaticPool is the key: it routes ALL connection requests to the same
    underlying sqlite3 connection, meaning tables created once stay visible.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # ← THE FIX: one connection = one DB
    )

    # Create all tables once
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


# ─────────────────────────────────────────────────────────────
# Session factory
# ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def db_session_factory(db_engine):
    """Async session factory bound to the shared engine."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# ─────────────────────────────────────────────────────────────
# Per-test DB session — rollback after each test
# ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db(db_session_factory) -> AsyncGenerator:
    """
    Provides a clean AsyncSession for each test.

    Uses a SAVEPOINT-based nested transaction so every test starts with
    a clean slate without recreating tables.

    Works because SQLite supports SAVEPOINT via BEGIN SAVEPOINT.
    """
    async with db_session_factory() as session:
        # Begin a SAVEPOINT so we can roll back to it after the test
        await session.begin_nested()
        try:
            yield session
        finally:
            await session.rollback()   # rolls back to SAVEPOINT


# ─────────────────────────────────────────────────────────────
# FastAPI test client
# ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_engine):
    """
    Async HTTPX test client wired to the FastAPI app with the test DB.
    Overrides the get_db dependency to use the shared in-memory engine.
    """
    try:
        from httpx import AsyncClient, ASGITransport
        from fastapi import FastAPI
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
        from app.main import app
        from app.core.database import get_db

        factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _override_get_db():
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = _override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

        app.dependency_overrides.clear()
    except ImportError:
        pytest.skip("httpx or app not available")


# ─── Auth token helpers ─────────────────────────────────────────────

@pytest.fixture
def analyst_token() -> str:
    from auth.auth import Role, create_token_pair
    return create_token_pair(sub="analyst@test.com", role=Role.ANALYST).access_token


@pytest.fixture
def admin_token() -> str:
    from auth.auth import Role, create_token_pair
    return create_token_pair(sub="admin@test.com", role=Role.ADMIN).access_token


@pytest.fixture
def analyst_headers(analyst_token: str) -> dict:
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ─────────────────────────────────────────────────────────────
# Sample data factories  (importable in any test module)
# ─────────────────────────────────────────────────────────────

def make_tx(
    tx_hash: str = "0x" + "d" * 64,
    chain: str = "ethereum",
    anomaly_score: float = 0.83,
    flagged: bool = True,
    from_address: str = "0x" + "a" * 40,
    to_address: str = "0x" + "b" * 40,
) -> dict:
    return {
        "tx_hash":       tx_hash,
        "chain":         chain,
        "block_number":  19_800_000,
        "from_address":  from_address,
        "to_address":    to_address,
        "value_eth":     1.5,
        "gas_price_gwei":42.1,
        "anomaly_score": anomaly_score,
        "gnn_risk_score":round(anomaly_score - 0.05, 4),
        "flagged":       flagged,
        "timestamp":     "2025-05-01T12:00:00Z",
    }


def make_alert(
    alert_id: str = "alert-001",
    severity: str = "HIGH",
    status:   str = "open",
    wallet:   str = "0x" + "a" * 40,
) -> dict:
    return {
        "id":          alert_id,
        "tx_hash":     "0x" + "d" * 64,
        "wallet":      wallet,
        "chain":       "ethereum",
        "severity":    severity,
        "status":      status,
        "score":       0.83,
        "assigned_to": None,
        "created_at":  "2025-05-01T12:05:00Z",
        "updated_at":  "2025-05-01T12:05:00Z",
    }


def make_user(
    email: str = "analyst@test.com",
    role:  str = "analyst",
) -> dict:
    return {"id": "user-001", "email": email, "role": role, "is_active": True}
