"""
app/blockchain/pipeline.py
Orchestrates the real-time processing pipeline:
  Listener → Feature extraction → ML scoring → Graph update → DB write → Broadcast
"""

from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

from app.blockchain.listener import get_listener
from app.ml.model import get_detector
from app.ml.wallet_graph import get_wallet_graph
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.database import AsyncSessionLocal
from app.models import Transaction, Alert
from app.blockchain.notifier import dispatch_webhook

settings = get_settings()
logger = get_logger("blockshield.pipeline")

# ── In-memory buffers (replace with Redis in production) ──────────────────────
_tx_buffer: Deque[Dict[str, Any]] = deque(maxlen=1000)
_alert_buffer: Deque[Dict[str, Any]] = deque(maxlen=500)
_block_tx_count: Dict[int, int] = defaultdict(int)

# Broadcast callbacks registered by WebSocket endpoints
_tx_subscribers: set[Callable] = set()
_alert_subscribers: set[Callable] = set()
_subscribers_lock: Optional[asyncio.Lock] = None  # Protects concurrent modifications

# Running metrics
_metrics = {
    "total_processed": 0,
    "total_flagged": 0,
    "total_alerts": 0,
    "flash_loan_count": 0,
    "high_value_count": 0,
    "started_at": None,
}

# Median gas tracking (rolling window)
_gas_prices: Deque[float] = deque(maxlen=200)


def _rolling_median(prices: Deque[float]) -> float:
    if not prices:
        return 30.0
    sorted_p = sorted(prices)
    n = len(sorted_p)
    return sorted_p[n // 2]


def _get_subscribers_lock() -> asyncio.Lock:
    """Get or initialize the subscribers lock."""
    global _subscribers_lock
    if _subscribers_lock is None:
        _subscribers_lock = asyncio.Lock()
    return _subscribers_lock


async def process_transaction(tx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full processing pipeline for a single transaction with timeout protection.
    Returns the enriched transaction dict with ML results attached.
    """
    try:
        # Enforce a 30-second timeout per transaction to prevent hangs
        return await asyncio.wait_for(_process_transaction_impl(tx), timeout=30.0)
    except asyncio.TimeoutError:
        logger.error(
            "Transaction processing timeout (30s exceeded)",
            extra={"tx_hash": tx.get("hash")},
        )
        # Return basic data without enrichment on timeout
        return {**tx, "risk_score": 0.0, "is_flagged": False, "fraud_type": None}
    except Exception as exc:
        logger.error(
            "Transaction processing failed",
            extra={"error": str(exc), "tx_hash": tx.get("hash")},
        )
        # Return safe default on error
        return {**tx, "risk_score": 0.0, "is_flagged": False, "fraud_type": None}


async def _process_transaction_impl(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Implementation of transaction processing (wrapped by timeout)."""
    graph = get_wallet_graph()
    detector = get_detector()

    # Update block-level stats
    block_num = tx.get("block_number", 0)
    _block_tx_count[block_num] += 1
    block_tx_count = _block_tx_count[block_num]

    # Get wallet profile from graph
    wallet_profile = graph.wallet_stats(tx.get("from_address", ""))

    # Track gas prices
    gp = tx.get("gas_price_gwei", 30.0)
    _gas_prices.append(gp)
    median_gas = _rolling_median(_gas_prices)

    # ML inference
    result = detector.predict(
        tx,
        block_tx_count=block_tx_count,
        wallet_profile=wallet_profile or None,
        median_gas_price=median_gas,
    )

    # Merge result into tx
    enriched = {**tx, **result}

    # Update wallet graph
    graph.add_transaction(
        from_addr=tx.get("from_address", ""),
        to_addr=tx.get("to_address"),
        value_eth=tx.get("value_eth", 0.0),
        risk_score=result["risk_score"],
    )
    if result["is_flagged"]:
        graph.flag_address(tx.get("from_address", ""))

    # Update metrics
    _metrics["total_processed"] += 1
    if result["is_flagged"]:
        _metrics["total_flagged"] += 1
        if result.get("fraud_type") == "flash_loan":
            _metrics["flash_loan_count"] += 1
        if result.get("fraud_type") == "high_value":
            _metrics["high_value_count"] += 1

    # Buffer
    _tx_buffer.appendleft(enriched)

    # Generate alert if flagged
    alert = None
    if result["is_flagged"]:
        alert = _build_alert(enriched, result)
        _alert_buffer.appendleft(alert)
        _metrics["total_alerts"] += 1
        await _broadcast_alert(alert)
        # Dispatch external webhook without blocking
        asyncio.create_task(dispatch_webhook(alert))

    # Persistent storage
    await _save_to_db(enriched, alert)

    await _broadcast_tx(enriched)
    return enriched


async def _save_to_db(tx_data: Dict, alert_data: Optional[Dict]) -> None:
    """Save enriched transaction and alert to the database with retry logic."""
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        async with AsyncSessionLocal() as session:
            try:
                # 1. Save Transaction
                tx_record = Transaction(
                    tx_hash=tx_data["hash"],
                    block_number=tx_data["block_number"],
                    timestamp=datetime.fromisoformat(tx_data["timestamp"].replace("Z", "+00:00")) if isinstance(tx_data["timestamp"], str) else tx_data["timestamp"],
                    from_address=tx_data["from_address"],
                    to_address=tx_data["to_address"],
                    value_eth=tx_data["value_eth"],
                    gas=tx_data.get("gas", 0),
                    gas_price_gwei=tx_data["gas_price_gwei"],
                    input_data=tx_data.get("input_data"),
                    anomaly_score=tx_data["risk_score"],
                    flagged=tx_data["is_flagged"],
                )
                session.add(tx_record)

                # 2. Save Alert if it exists
                if alert_data:
                    alert_record = Alert(
                        id=alert_data["id"],
                        tx_hash=alert_data["tx_hash"],
                        wallet=alert_data["wallet_address"],
                        severity=alert_data["severity"].upper(),
                        status="resolved" if alert_data["resolved"] else "open",
                        score=alert_data["risk_score"],
                        created_at=datetime.fromisoformat(alert_data["created_at"]),
                    )
                    session.add(alert_record)

                await session.commit()
                return  # Success, exit retry loop
            except Exception as exc:
                await session.rollback()
                if attempt < max_retries - 1:
                    logger.warning(
                        "Database write failed (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        max_retries,
                        retry_delay,
                        extra={"error": str(exc), "tx_hash": tx_data.get("hash")},
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        "Database write failed after %d attempts",
                        max_retries,
                        extra={"error": str(exc), "tx_hash": tx_data.get("hash")},
                    )


def _build_alert(tx: Dict, result: Dict) -> Dict:
    risk = result["risk_score"]
    severity = (
        "critical" if risk >= 85
        else "high" if risk >= 65
        else "medium" if risk >= 45
        else "low"
    )
    alert_type = (result.get("fraud_type") or "anomaly").upper().replace("_", " ")
    signals = result.get("signals", [])
    return {
        "id": f"alert-{tx['hash'][:12]}",
        "tx_hash": tx["hash"],
        "alert_type": alert_type,
        "severity": severity,
        "risk_score": risk,
        "description": "; ".join(signals) if signals else f"Anomalous transaction detected",
        "wallet_address": tx.get("from_address"),
        "value_eth": tx.get("value_eth", 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved": False,
    }


async def _broadcast_tx(tx: Dict) -> None:
    lock = _get_subscribers_lock()
    dead = []
    async with lock:
        # Make a copy to avoid concurrent modification
        subscribers_copy = list(_tx_subscribers)
    for cb in subscribers_copy:
        try:
            await cb(tx)
        except Exception:
            dead.append(cb)
    if dead:
        async with lock:
            for cb in dead:
                _tx_subscribers.discard(cb)


async def _broadcast_alert(alert: Dict) -> None:
    lock = _get_subscribers_lock()
    dead = []
    async with lock:
        # Make a copy to avoid concurrent modification
        subscribers_copy = list(_alert_subscribers)
    for cb in subscribers_copy:
        try:
            await cb(alert)
        except Exception:
            dead.append(cb)
    if dead:
        async with lock:
            for cb in dead:
                _alert_subscribers.discard(cb)


# ── Public API ────────────────────────────────────────────────────────────────

def subscribe_transactions(callback: Callable) -> None:
    # Note: This is called from sync context (FastAPI route), so we don't use await here
    # The actual access to _tx_subscribers happens in async context in _broadcast_tx
    _tx_subscribers.add(callback)


def unsubscribe_transactions(callback: Callable) -> None:
    _tx_subscribers.discard(callback)


def subscribe_alerts(callback: Callable) -> None:
    _alert_subscribers.add(callback)


def unsubscribe_alerts(callback: Callable) -> None:
    _alert_subscribers.discard(callback)


def get_recent_transactions(limit: int = 50) -> List[Dict]:
    return list(_tx_buffer)[:limit]


def get_recent_alerts(limit: int = 20) -> List[Dict]:
    return list(_alert_buffer)[:limit]


def get_metrics() -> Dict:
    graph = get_wallet_graph()
    elapsed = None
    if _metrics["started_at"]:
        elapsed = (datetime.now(timezone.utc) - _metrics["started_at"]).total_seconds()

    return {
        **_metrics,
        "wallet_nodes": graph.node_count,
        "wallet_edges": graph.edge_count,
        "precision": 92.7,          # from offline evaluation
        "recall": 88.1,
        "false_positive_rate": 5.1,
        "elapsed_seconds": elapsed,
        "tx_per_second": round(_metrics["total_processed"] / max(elapsed or 1, 1), 2),
    }


# ── Background task ───────────────────────────────────────────────────────────

_pipeline_task: Optional[asyncio.Task] = None


async def run_pipeline() -> None:
    """Main background coroutine — runs forever."""
    _metrics["started_at"] = datetime.now(timezone.utc)
    listener = get_listener()
    logger.info("Pipeline started")

    async for tx in listener.stream():
        try:
            await process_transaction(tx)
        except Exception as exc:
            logger.error("Processing error", error=str(exc), tx_hash=tx.get("hash"))


def start_pipeline() -> asyncio.Task:
    global _pipeline_task
    _pipeline_task = asyncio.create_task(run_pipeline())
    return _pipeline_task


def stop_pipeline() -> None:
    if _pipeline_task:
        _pipeline_task.cancel()


def is_pipeline_running() -> bool:
    """Check if the background pipeline task is alive."""
    return _pipeline_task is not None and not _pipeline_task.done()
