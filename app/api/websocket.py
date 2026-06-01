"""
app/api/websocket.py
WebSocket endpoints for real-time transaction and alert streaming.

Clients connect and receive JSON messages as events arrive:
  /ws/stream  → all transactions (with risk scores)
  /ws/alerts  → flagged transactions / alerts only
"""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.blockchain.pipeline import (
    subscribe_transactions, unsubscribe_transactions,
    subscribe_alerts, unsubscribe_alerts,
    get_recent_transactions, get_recent_alerts,
)
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger("blockshield.ws")


def _safe_serialize(obj):
    """JSON-serialise a transaction dict, converting datetime to ISO strings."""
    import datetime
    result = {}
    for k, v in obj.items():
        if isinstance(v, datetime.datetime):
            result[k] = v.isoformat()
        elif isinstance(v, bytes):
            result[k] = v.hex()
        else:
            result[k] = v
    return result


@router.websocket("/ws/stream")
async def transaction_stream(websocket: WebSocket):
    """
    Real-time transaction stream.
    Sends all incoming transactions as JSON.
    """
    await websocket.accept()
    logger.info("WS client connected (stream)")

    queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    async def enqueue(tx):
        try:
            queue.put_nowait(_safe_serialize(tx))
        except asyncio.QueueFull:
            pass  # drop if client is too slow

    subscribe_transactions(enqueue)

    # Send recent transactions first (catchup)
    for tx in get_recent_transactions(limit=20):
        await websocket.send_text(json.dumps(_safe_serialize(tx)))

    async def send_loop():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(msg))
            except asyncio.TimeoutError:
                # Heartbeat ping
                await websocket.send_text(json.dumps({"type": "ping"}))

    async def receive_loop():
        try:
            while True:
                # Await client messages to keep connection alive and detect disconnects
                data = await websocket.receive_text()
                # Handle pongs or other client signals
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "pong":
                        continue
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            logger.info(f"WS receive loop error: {exc}")

    try:
        tasks = [
            asyncio.create_task(send_loop(), name="send_loop"),
            asyncio.create_task(receive_loop(), name="receive_loop")
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except (WebSocketDisconnect, Exception) as exc:
        logger.info(f"WS client disconnected (stream) - reason: {exc}")
    finally:
        unsubscribe_transactions(enqueue)


@router.websocket("/ws/alerts")
async def alert_stream(websocket: WebSocket):
    """
    Real-time alert stream — only sends flagged/suspicious transactions.
    """
    await websocket.accept()
    logger.info("WS client connected (alerts)")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def enqueue(alert):
        try:
            queue.put_nowait(_safe_serialize(alert))
        except asyncio.QueueFull:
            pass

    subscribe_alerts(enqueue)

    # Send recent alerts first
    for alert in get_recent_alerts(limit=10):
        await websocket.send_text(json.dumps(_safe_serialize(alert)))

    async def send_loop():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(msg))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))

    async def receive_loop():
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "pong":
                        continue
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            raise
        except Exception as exc:
            logger.info(f"WS alert receive loop error: {exc}")

    try:
        tasks = [
            asyncio.create_task(send_loop(), name="alert_send_loop"),
            asyncio.create_task(receive_loop(), name="alert_receive_loop")
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except (WebSocketDisconnect, Exception) as exc:
        logger.info(f"WS client disconnected (alerts) - reason: {exc}")
    finally:
        unsubscribe_alerts(enqueue)
