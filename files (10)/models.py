"""
app/models.py
─────────────
SQLAlchemy ORM models for BlockShield.

ALL models live here so that:
  • alembic env.py can do: from app.models import Base
  • any route/service can do: from app.models import Transaction, Alert, User …

Tables:
  users, transactions, alerts, alert_comments,
  alert_rules, analyst_feedback, model_versions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, Numeric, SmallInteger, String, Text,
    func, text,
)
# JSONB on PostgreSQL, JSON on SQLite — resolved at engine creation time
from sqlalchemy import JSON
try:
    from sqlalchemy.dialects.postgresql import JSONB  # type: ignore[import]
except ImportError:
    JSONB = JSON  # type: ignore[assignment]
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ─── Base ────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Users ───────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:              Mapped[str]  = mapped_column(String(36),  primary_key=True, default=_uuid)
    email:           Mapped[str]  = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str]  = mapped_column(String(255), nullable=False)
    full_name:       Mapped[str | None] = mapped_column(String(255))
    role:            Mapped[str]  = mapped_column(String(32),  nullable=False, server_default="analyst")
    is_active:       Mapped[bool] = mapped_column(Boolean,     nullable=False, server_default=text("true"))
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"


# ─── Transactions ─────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id:             Mapped[int]   = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tx_hash:        Mapped[str]   = mapped_column(String(66),  nullable=False, unique=True, index=True)
    chain:          Mapped[str]   = mapped_column(String(32),  nullable=False, server_default="ethereum", index=True)
    block_number:   Mapped[int | None]   = mapped_column(BigInteger)
    from_address:   Mapped[str]   = mapped_column(String(42),  nullable=False, index=True)
    to_address:     Mapped[str | None]   = mapped_column(String(42), index=True)
    value_eth:      Mapped[float] = mapped_column(Numeric(36, 18), nullable=False, server_default=text("0"))
    gas:            Mapped[int | None]   = mapped_column(BigInteger)
    gas_price_gwei: Mapped[float | None] = mapped_column(Numeric(20, 9))
    input_data:     Mapped[str | None]   = mapped_column(Text)
    anomaly_score:  Mapped[float | None] = mapped_column(Float, index=True)
    gnn_risk_score: Mapped[float | None] = mapped_column(Float)
    flagged:        Mapped[bool]  = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    community_id:   Mapped[int | None]   = mapped_column(Integer)
    features_json:  Mapped[dict | None]  = mapped_column(JSONB)
    timestamp:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<Transaction {self.tx_hash[:12]}… score={self.anomaly_score}>"


# ─── Alerts ──────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id:              Mapped[str]  = mapped_column(String(36),  primary_key=True, default=_uuid)
    tx_hash:         Mapped[str | None]  = mapped_column(String(66))
    wallet:          Mapped[str | None]  = mapped_column(String(42), index=True)
    chain:           Mapped[str]  = mapped_column(String(32),  nullable=False, server_default="ethereum")
    severity:        Mapped[str]  = mapped_column(String(16),  nullable=False, server_default="HIGH", index=True)
    status:          Mapped[str]  = mapped_column(String(16),  nullable=False, server_default="open",  index=True)
    rule_id:         Mapped[str | None]  = mapped_column(String(36))
    score:           Mapped[float | None] = mapped_column(Float)
    assigned_to:     Mapped[str | None]  = mapped_column(String(128))
    resolution:      Mapped[str | None]  = mapped_column(String(32))
    resolution_note: Mapped[str | None]  = mapped_column(Text)
    resolved_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    comments: Mapped[list["AlertComment"]] = relationship(
        "AlertComment", back_populates="alert", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Alert {self.id} {self.severity} {self.status}>"


class AlertComment(Base):
    __tablename__ = "alert_comments"

    id:          Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id:    Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    analyst_id:  Mapped[str] = mapped_column(String(128), nullable=False)
    text:        Mapped[str] = mapped_column(Text, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    alert: Mapped["Alert"] = relationship("Alert", back_populates="comments")


# ─── Alert Rules ──────────────────────────────────────────────

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id:          Mapped[str]  = mapped_column(String(36),  primary_key=True, default=_uuid)
    name:        Mapped[str]  = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity:    Mapped[str]  = mapped_column(String(16),  nullable=False, server_default="HIGH", index=True)
    rule_json:   Mapped[dict] = mapped_column(JSONB, nullable=False)
    active:      Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), index=True)
    created_by:  Mapped[str | None] = mapped_column(String(128))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ─── Analyst Feedback ─────────────────────────────────────────

class AnalystFeedback(Base):
    __tablename__ = "analyst_feedback"

    id:             Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tx_hash:        Mapped[str] = mapped_column(String(66),  nullable=False, unique=True)
    wallet_address: Mapped[str] = mapped_column(String(42),  nullable=False, index=True)
    label:          Mapped[int] = mapped_column(SmallInteger, nullable=False)   # 0=safe 1=risky
    analyst_id:     Mapped[str] = mapped_column(String(128), nullable=False)
    features:       Mapped[dict | None] = mapped_column(JSONB)
    retrain_used:   Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    timestamp:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


# ─── Model Versions ───────────────────────────────────────────

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id:            Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_type:    Mapped[str] = mapped_column(String(64),  nullable=False, index=True)  # isolation_forest | gnn
    version:       Mapped[int] = mapped_column(Integer,     nullable=False)
    labels_used:   Mapped[int | None]   = mapped_column(Integer)
    training_rows: Mapped[int | None]   = mapped_column(Integer)
    contamination: Mapped[float | None] = mapped_column(Float)
    artifact_path: Mapped[str | None]   = mapped_column(String(512))
    metrics_json:  Mapped[dict | None]  = mapped_column(JSONB)
    trained_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
