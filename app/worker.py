"""
app/worker.py
─────────────
BlockShield background pipeline worker.

Started by docker-compose as:
    command: python -m app.worker

Responsibilities:
  1. Subscribe to the 'transactions' broker topic
  2. For each message:
       a. Run FeatureEngineer  → build feature dict
       b. Score with LiveIsolationForest  (anomaly_score)
       c. Score with WalletGNN if available  (gnn_risk_score)
       d. Evaluate all active AlertRules
       e. Persist enriched transaction to DB
       f. Publish flagged txs to 'alerts' topic
       g. Update Prometheus metrics
  3. Run RetrainScheduler in a parallel task

Graceful shutdown on SIGINT / SIGTERM.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ─── Resolve project root so relative imports work ────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─────────────────────────────────────────────────────────────
# Worker class
# ─────────────────────────────────────────────────────────────

class PipelineWorker:
    """
    Async pipeline worker that processes incoming transaction messages.
    Each method is independently replaceable for testing.
    """

    def __init__(self):
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self) -> None:
        from app.core.config import settings
        from broker.message_broker import get_broker
        from ml.feedback_loop import LiveIsolationForest, FeedbackStore, RetrainScheduler

        logger.info("PipelineWorker starting …")
        self._running = True

        # Broker
        self._broker = get_broker(settings.BROKER_BACKEND)
        await self._broker.connect()

        # Live model (loads from disk if available)
        self._live_model = LiveIsolationForest()
        self._live_model.load_from_disk()

        # Feature engineer
        from ml.feature_engineering import FeatureEngineer
        self._engineer = FeatureEngineer()
        await self._engineer.load_ofac_list()

        # Feedback store + retrain scheduler
        self._feedback_store = FeedbackStore()
        self._scheduler = RetrainScheduler(
            store=self._feedback_store,
            live_model=self._live_model,
            raw_feature_fetcher=self._fetch_raw_features,
        )

        # Kick off tasks
        self._tasks = [
            asyncio.create_task(self._consume_transactions(), name="consumer"),
            asyncio.create_task(self._scheduler.run(),        name="retrain_scheduler"),
            asyncio.create_task(self._health_heartbeat(),     name="heartbeat"),
        ]

        logger.info("PipelineWorker running. Tasks: %s", [t.get_name() for t in self._tasks])

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("PipelineWorker: tasks cancelled, shutting down.")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._broker.close()
        logger.info("PipelineWorker stopped.")

    # ── Main consumer loop ───────────────────────────────────

    async def _consume_transactions(self) -> None:
        logger.info("Consumer: subscribing to 'transactions' topic …")
        while self._running:
            try:
                async for message in self._broker.subscribe("transactions"):
                    if not self._running:
                        break
                    try:
                        await self._process(message.payload)
                    except Exception as exc:
                        logger.exception("Consumer: failed to process message %s: %s", message.message_id, exc)
                        try:
                            from observability.observability import metrics
                            metrics.tx_failed.labels(chain=message.payload.get("chain","?"), reason=type(exc).__name__).inc()
                        except Exception:
                            pass
            except Exception as exc:
                if self._running:
                    logger.error("Consumer: broker subscription dropped, reconnecting in 5s: %s", exc)
                    await asyncio.sleep(5)

    # ── Single transaction processing ────────────────────────

    async def _process(self, tx: Dict[str, Any]) -> None:
        chain    = tx.get("chain", "ethereum")
        tx_hash  = tx.get("hash") or tx.get("tx_hash", "")
        from_addr = tx.get("from", "")

        # 1. Build features
        features = await self._engineer.build_features(
            wallet_address=from_addr,
            transactions=[tx],
        )

        # 2. Isolation Forest score
        anomaly_score = 0.0
        try:
            _, anomaly_score = self._live_model.predict(features)
        except RuntimeError:
            pass  # model not loaded yet

        # 3. GNN score (optional)
        gnn_score: float | None = None
        # GNN scoring runs asynchronously on a separate schedule;
        # set via a cached lookup or leave None for deferred computation.

        flagged = anomaly_score > float(os.getenv("FLAG_THRESHOLD", "0.6"))

        # 4. Evaluate alert rules
        alerts = await self._evaluate_rules(tx, features, anomaly_score)

        # 5. Persist to DB
        await self._persist_transaction(tx, features, anomaly_score, gnn_score, flagged)

        # 6. Publish alerts
        for alert in alerts:
            from broker.message_broker import BrokerMessage
            await self._broker.publish("alerts", BrokerMessage(payload=alert))

        # 7. Metrics
        try:
            from observability.observability import metrics
            metrics.tx_processed.labels(chain=chain).inc()
            metrics.anomaly_score.observe(anomaly_score)
            if flagged:
                metrics.tx_flagged_anomaly.labels(chain=chain, model="isolation_forest").inc()
        except Exception:
            pass

        if flagged:
            logger.info("FLAGGED tx=%s chain=%s score=%.3f", tx_hash[:12], chain, anomaly_score)

    # ── Alert rule evaluation ────────────────────────────────

    async def _evaluate_rules(
        self,
        tx: Dict[str, Any],
        features: Dict[str, float],
        anomaly_score: float,
    ) -> list[Dict[str, Any]]:
        """
        Load active rules from DB, evaluate each against the feature vector,
        return list of alert dicts for any rules that fire.
        """
        triggered = []
        try:
            from app.core.database import AsyncSessionLocal
            from app.models import AlertRule
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AlertRule).where(AlertRule.active == True)  # noqa: E712
                )
                rules = result.scalars().all()

            ctx = {**features, "anomaly_score": anomaly_score, "value_eth": float(tx.get("value", 0)) / 1e18}

            for rule in rules:
                if self._rule_matches(rule.rule_json, ctx):
                    triggered.append({
                        "rule_id":   str(rule.id),
                        "rule_name": rule.name,
                        "severity":  rule.severity,
                        "tx_hash":   tx.get("hash", ""),
                        "wallet":    tx.get("from", ""),
                        "chain":     tx.get("chain", "ethereum"),
                        "score":     anomaly_score,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        except Exception as exc:
            logger.debug("Rule evaluation skipped: %s", exc)
        return triggered

    def _rule_matches(self, rule_json: dict, ctx: Dict[str, float]) -> bool:
        """Evaluate a rule's condition groups (AND/OR logic) against ctx."""
        try:
            groups = rule_json.get("groups", [])
            # Top-level groups are OR'd together
            for group in groups:
                logic      = group.get("logic", "AND")
                conditions = group.get("conditions", [])
                results    = [self._eval_condition(c, ctx) for c in conditions]
                group_pass = all(results) if logic == "AND" else any(results)
                if group_pass:
                    return True
            return False
        except Exception:
            return False

    def _eval_condition(self, cond: dict, ctx: Dict[str, float]) -> bool:
        field    = cond.get("field", "")
        operator = cond.get("operator", ">")
        try:
            value = float(cond.get("value", 0))
        except ValueError:
            value = 0.0
        actual = ctx.get(field, 0.0)
        ops = {">": actual > value, ">=": actual >= value, "<": actual < value,
               "<=": actual <= value, "==": actual == value, "!=": actual != value}
        return ops.get(operator, False)

    # ── DB persistence ────────────────────────────────────────

    async def _persist_transaction(
        self,
        tx: Dict[str, Any],
        features: Dict[str, float],
        anomaly_score: float,
        gnn_score: float | None,
        flagged: bool,
    ) -> None:
        try:
            from app.core.database import AsyncSessionLocal
            from app.models import Transaction

            async with AsyncSessionLocal() as session:
                existing = await session.get(Transaction, tx.get("hash", ""))
                if existing:
                    return  # already persisted (duplicate block delivery)

                record = Transaction(
                    tx_hash       = tx.get("hash", ""),
                    chain         = tx.get("chain", "ethereum"),
                    block_number  = int(tx.get("blockNumber", 0), 16) if isinstance(tx.get("blockNumber"), str) else tx.get("blockNumber"),
                    from_address  = tx.get("from", ""),
                    to_address    = tx.get("to"),
                    value_eth     = float(tx.get("value", 0)) / 1e18 if isinstance(tx.get("value"), (str, int)) else 0,
                    gas           = int(tx.get("gas", "0x0"), 16) if isinstance(tx.get("gas"), str) else tx.get("gas"),
                    gas_price_gwei= features.get("avg_gas_price", 0),
                    anomaly_score = anomaly_score,
                    gnn_risk_score= gnn_score,
                    flagged       = flagged,
                    features_json = features,
                    timestamp     = datetime.now(timezone.utc),
                )
                session.add(record)
                await session.commit()
        except Exception as exc:
            logger.warning("persist_transaction failed: %s", exc)

    # ── Raw feature fetcher (for retraining) ──────────────────

    async def _fetch_raw_features(self) -> list[Dict[str, float]]:
        try:
            from app.core.database import AsyncSessionLocal
            from app.models import Transaction
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Transaction.features_json)
                    .where(Transaction.features_json.isnot(None))
                    .order_by(Transaction.created_at.desc())
                    .limit(100_000)
                )
                rows = result.scalars().all()
            return [r for r in rows if r]
        except Exception as exc:
            logger.warning("fetch_raw_features failed: %s", exc)
            return []

    # ── Heartbeat ─────────────────────────────────────────────

    async def _health_heartbeat(self) -> None:
        while self._running:
            logger.debug("PipelineWorker heartbeat OK")
            await asyncio.sleep(60)


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

async def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = PipelineWorker()

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()

    def _signal_handler():
        logger.info("Shutdown signal received.")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
