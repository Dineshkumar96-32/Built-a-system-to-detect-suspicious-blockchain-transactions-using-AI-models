"""
tests/db/test_db_operations.py
───────────────────────────────
Database CRUD tests for all BlockShield models.
Uses in-memory SQLite so no external DB is required.

Run:
    pytest tests/db/test_db_operations.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert, AlertComment, AlertRule, AnalystFeedback,
    ModelVersion, Transaction, User,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _tx(**kw) -> Transaction:
    defaults = dict(
        tx_hash="0x" + "d" * 64, chain="ethereum",
        block_number=19_800_000, from_address="0x" + "a" * 40,
        to_address="0x" + "b" * 40, value_eth=1.5,
        anomaly_score=0.83, flagged=True,
    )
    return Transaction(**{**defaults, **kw})


def _user(**kw) -> User:
    defaults = dict(
        email="analyst@test.com",
        hashed_password="$2b$12$fake_hash",
        role="analyst",
    )
    return User(**{**defaults, **kw})


def _alert(**kw) -> Alert:
    defaults = dict(
        tx_hash="0x" + "d" * 64, wallet="0x" + "a" * 40,
        chain="ethereum", severity="HIGH", status="open", score=0.83,
    )
    return Alert(**{**defaults, **kw})


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models import Base
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────

class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db):
        user = _user()
        db.add(user)
        await db.flush()
        assert user.id is not None
        assert user.role == "analyst"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_user_email_unique(self, db):
        import sqlalchemy.exc
        db.add(_user(email="dup@test.com"))
        await db.flush()
        db.add(_user(email="dup@test.com"))
        with pytest.raises(Exception):  # IntegrityError
            await db.flush()

    @pytest.mark.asyncio
    async def test_query_user_by_email(self, db):
        db.add(_user(email="findme@test.com"))
        await db.flush()
        result = await db.execute(select(User).where(User.email == "findme@test.com"))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.email == "findme@test.com"


# ─────────────────────────────────────────────────────────────
# Transaction
# ─────────────────────────────────────────────────────────────

class TestTransactionModel:
    @pytest.mark.asyncio
    async def test_create_transaction(self, db):
        tx = _tx()
        db.add(tx)
        await db.flush()
        assert tx.id is not None

    @pytest.mark.asyncio
    async def test_tx_hash_unique(self, db):
        db.add(_tx(tx_hash="0x" + "e" * 64))
        await db.flush()
        db.add(_tx(tx_hash="0x" + "e" * 64))
        with pytest.raises(Exception):
            await db.flush()

    @pytest.mark.asyncio
    async def test_filter_flagged(self, db):
        h1 = "0x" + "f1" + "a" * 62
        h2 = "0x" + "f2" + "a" * 62
        db.add(_tx(tx_hash=h1, flagged=True,  anomaly_score=0.91))
        db.add(_tx(tx_hash=h2, flagged=False, anomaly_score=0.21))
        await db.flush()
        result = await db.execute(select(Transaction).where(Transaction.flagged == True))  # noqa
        flagged = result.scalars().all()
        hashes = [t.tx_hash for t in flagged]
        assert h1 in hashes
        assert h2 not in hashes

    @pytest.mark.asyncio
    async def test_filter_by_chain(self, db):
        db.add(_tx(tx_hash="0x" + "cc" + "a" * 62, chain="polygon"))
        await db.flush()
        result = await db.execute(select(Transaction).where(Transaction.chain == "polygon"))
        rows = result.scalars().all()
        assert all(t.chain == "polygon" for t in rows)

    @pytest.mark.asyncio
    async def test_anomaly_score_range(self, db):
        db.add(_tx(tx_hash="0x" + "sc" + "a" * 62, anomaly_score=0.95))
        await db.flush()
        result = await db.execute(
            select(Transaction).where(Transaction.anomaly_score > 0.9)
        )
        high = result.scalars().all()
        assert any(t.anomaly_score > 0.9 for t in high)


# ─────────────────────────────────────────────────────────────
# Alert + AlertComment
# ─────────────────────────────────────────────────────────────

class TestAlertModel:
    @pytest.mark.asyncio
    async def test_create_alert(self, db):
        alert = _alert()
        db.add(alert)
        await db.flush()
        assert alert.id is not None
        assert alert.status == "open"

    @pytest.mark.asyncio
    async def test_alert_status_update(self, db):
        alert = _alert()
        db.add(alert)
        await db.flush()
        alert.status     = "assigned"
        alert.assigned_to = "alice@test.com"
        await db.flush()
        result = await db.execute(select(Alert).where(Alert.id == alert.id))
        refreshed = result.scalar_one()
        assert refreshed.status == "assigned"
        assert refreshed.assigned_to == "alice@test.com"

    @pytest.mark.asyncio
    async def test_alert_comment_cascade(self, db):
        alert = _alert()
        db.add(alert)
        await db.flush()

        comment = AlertComment(
            alert_id=alert.id, analyst_id="bob@test.com", text="Investigating."
        )
        db.add(comment)
        await db.flush()

        result = await db.execute(
            select(AlertComment).where(AlertComment.alert_id == alert.id)
        )
        comments = result.scalars().all()
        assert len(comments) >= 1
        assert comments[0].text == "Investigating."

    @pytest.mark.asyncio
    async def test_filter_by_severity(self, db):
        db.add(_alert(severity="CRITICAL"))
        await db.flush()
        result = await db.execute(select(Alert).where(Alert.severity == "CRITICAL"))
        crits = result.scalars().all()
        assert all(a.severity == "CRITICAL" for a in crits)


# ─────────────────────────────────────────────────────────────
# AlertRule
# ─────────────────────────────────────────────────────────────

class TestAlertRuleModel:
    @pytest.mark.asyncio
    async def test_create_rule(self, db):
        rule = AlertRule(
            name="High Score",
            severity="HIGH",
            rule_json={"groups": [{"logic": "AND", "conditions": [{"field": "anomaly_score", "operator": ">", "value": "0.8"}]}]},
            active=True,
        )
        db.add(rule)
        await db.flush()
        assert rule.id is not None

    @pytest.mark.asyncio
    async def test_toggle_rule(self, db):
        rule = AlertRule(name="Toggle Test", severity="LOW", rule_json={}, active=True)
        db.add(rule)
        await db.flush()
        rule.active = False
        await db.flush()
        result = await db.execute(select(AlertRule).where(AlertRule.id == rule.id))
        assert result.scalar_one().active is False


# ─────────────────────────────────────────────────────────────
# AnalystFeedback
# ─────────────────────────────────────────────────────────────

class TestAnalystFeedback:
    @pytest.mark.asyncio
    async def test_create_feedback(self, db):
        fb = AnalystFeedback(
            tx_hash="0x" + "fb" + "a" * 62,
            wallet_address="0x" + "a" * 40,
            label=1,
            analyst_id="carol@test.com",
            features={"anomaly_score": 0.85},
        )
        db.add(fb)
        await db.flush()
        assert fb.id is not None
        assert fb.retrain_used is False

    @pytest.mark.asyncio
    async def test_mark_retrain_used(self, db):
        fb = AnalystFeedback(
            tx_hash="0x" + "fb2" + "a" * 61,
            wallet_address="0x" + "a" * 40,
            label=0, analyst_id="carol@test.com",
        )
        db.add(fb)
        await db.flush()
        fb.retrain_used = True
        await db.flush()
        result = await db.execute(
            select(AnalystFeedback).where(AnalystFeedback.id == fb.id)
        )
        assert result.scalar_one().retrain_used is True

    @pytest.mark.asyncio
    async def test_filter_pending_retrain(self, db):
        db.add(AnalystFeedback(
            tx_hash="0x" + "pnd" + "a" * 61,
            wallet_address="0x" + "a" * 40,
            label=1, analyst_id="dave@test.com", retrain_used=False,
        ))
        await db.flush()
        result = await db.execute(
            select(AnalystFeedback).where(AnalystFeedback.retrain_used == False)  # noqa
        )
        pending = result.scalars().all()
        assert len(pending) >= 1


# ─────────────────────────────────────────────────────────────
# ModelVersion
# ─────────────────────────────────────────────────────────────

class TestModelVersion:
    @pytest.mark.asyncio
    async def test_create_model_version(self, db):
        mv = ModelVersion(
            model_type="isolation_forest",
            version=7,
            training_rows=84_200,
            labels_used=350,
            contamination=0.08,
            metrics_json={"val_acc": 0.94},
        )
        db.add(mv)
        await db.flush()
        assert mv.id is not None

    @pytest.mark.asyncio
    async def test_latest_version_query(self, db):
        from sqlalchemy import desc
        db.add(ModelVersion(model_type="gnn", version=1, training_rows=1000))
        db.add(ModelVersion(model_type="gnn", version=2, training_rows=2000))
        await db.flush()
        result = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_type == "gnn")
            .order_by(desc(ModelVersion.version))
            .limit(1)
        )
        latest = result.scalar_one()
        assert latest.version >= 2
