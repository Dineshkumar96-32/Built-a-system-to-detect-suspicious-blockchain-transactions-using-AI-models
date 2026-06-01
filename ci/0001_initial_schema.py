"""Initial schema — users, transactions, alerts, alert_rules

Revision ID: 0001
Revises:
Create Date: 2025-05-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "0001"
down_revision = None
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("email",           sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name",       sa.String(255), nullable=True),
        sa.Column("role",            sa.String(32),  nullable=False, server_default="analyst"),
        sa.Column("is_active",       sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("last_login",      sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── transactions ───────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id",              sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tx_hash",         sa.String(66),   nullable=False, unique=True),
        sa.Column("chain",           sa.String(32),   nullable=False, server_default="ethereum"),
        sa.Column("block_number",    sa.BigInteger(), nullable=True),
        sa.Column("from_address",    sa.String(42),   nullable=False),
        sa.Column("to_address",      sa.String(42),   nullable=True),
        sa.Column("value_eth",       sa.Numeric(36,18), nullable=False, server_default="0"),
        sa.Column("gas",             sa.BigInteger(), nullable=True),
        sa.Column("gas_price_gwei",  sa.Numeric(20,9), nullable=True),
        sa.Column("input_data",      sa.Text(),       nullable=True),
        sa.Column("anomaly_score",   sa.Float(),      nullable=True),
        sa.Column("gnn_risk_score",  sa.Float(),      nullable=True),
        sa.Column("flagged",         sa.Boolean(),    nullable=False, server_default="false"),
        sa.Column("community_id",    sa.Integer(),    nullable=True),
        sa.Column("features_json",   postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp",       sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tx_hash",             "transactions", ["tx_hash"])
    op.create_index("ix_tx_from_address",     "transactions", ["from_address"])
    op.create_index("ix_tx_to_address",       "transactions", ["to_address"])
    op.create_index("ix_tx_chain_timestamp",  "transactions", ["chain", "timestamp"])
    op.create_index("ix_tx_flagged",          "transactions", ["flagged"])
    op.create_index("ix_tx_anomaly_score",    "transactions", ["anomaly_score"])
    op.create_index(
        "ix_tx_high_risk",
        "transactions",
        ["anomaly_score", "created_at"],
        postgresql_where=sa.text("anomaly_score > 0.5"),
    )

    # ── alerts ─────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id",           sa.String(36),  primary_key=True),
        sa.Column("tx_hash",      sa.String(66),  nullable=True),
        sa.Column("wallet",       sa.String(42),  nullable=True),
        sa.Column("chain",        sa.String(32),  nullable=False, server_default="ethereum"),
        sa.Column("severity",     sa.String(16),  nullable=False, server_default="HIGH"),
        sa.Column("status",       sa.String(16),  nullable=False, server_default="open"),
        sa.Column("rule_id",      sa.String(16),  nullable=True),
        sa.Column("score",        sa.Float(),     nullable=True),
        sa.Column("assigned_to",  sa.String(128), nullable=True),
        sa.Column("resolution",   sa.String(32),  nullable=True),
        sa.Column("resolved_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_alerts_status",    "alerts", ["status"])
    op.create_index("ix_alerts_severity",  "alerts", ["severity"])
    op.create_index("ix_alerts_wallet",    "alerts", ["wallet"])
    op.create_index("ix_alerts_created",   "alerts", ["created_at"])

    # ── alert_comments ─────────────────────────────────────────
    op.create_table(
        "alert_comments",
        sa.Column("id",          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("alert_id",    sa.String(36),   nullable=False),
        sa.Column("analyst_id",  sa.String(128),  nullable=False),
        sa.Column("text",        sa.Text(),       nullable=False),
        sa.Column("created_at",  sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_comments_alert_id", "alert_comments", ["alert_id"])

    # ── alert_rules ────────────────────────────────────────────
    op.create_table(
        "alert_rules",
        sa.Column("id",           sa.String(16),  primary_key=True),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("description",  sa.Text(),      nullable=True),
        sa.Column("severity",     sa.String(16),  nullable=False, server_default="HIGH"),
        sa.Column("rule_json",    postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active",       sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_by",   sa.String(128), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_rules_active",   "alert_rules", ["active"])
    op.create_index("ix_rules_severity", "alert_rules", ["severity"])

    # ── analyst_feedback ───────────────────────────────────────
    op.create_table(
        "analyst_feedback",
        sa.Column("id",              sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tx_hash",         sa.String(66),   nullable=False, unique=True),
        sa.Column("wallet_address",  sa.String(42),   nullable=False),
        sa.Column("label",           sa.SmallInteger(), nullable=False),
        sa.Column("analyst_id",      sa.String(128),  nullable=False),
        sa.Column("features",        postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retrain_used",    sa.Boolean(),    nullable=False, server_default="false"),
        sa.Column("timestamp",       sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_feedback_wallet",       "analyst_feedback", ["wallet_address"])
    op.create_index("ix_feedback_retrain_used", "analyst_feedback", ["retrain_used"])

    # ── model_versions ─────────────────────────────────────────
    op.create_table(
        "model_versions",
        sa.Column("id",              sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_type",      sa.String(64),   nullable=False),
        sa.Column("version",         sa.Integer(),    nullable=False),
        sa.Column("labels_used",     sa.Integer(),    nullable=True),
        sa.Column("training_rows",   sa.Integer(),    nullable=True),
        sa.Column("contamination",   sa.Float(),      nullable=True),
        sa.Column("artifact_path",   sa.String(512),  nullable=True),
        sa.Column("metrics_json",    postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trained_at",      sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("analyst_feedback")
    op.drop_table("alert_rules")
    op.drop_table("alert_comments")
    op.drop_table("alerts")
    op.drop_table("transactions")
    op.drop_table("users")
