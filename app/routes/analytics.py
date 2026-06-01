"""
app/routes/analytics.py
────────────────────────
Analytics endpoints.

GET /analytics/heatmap   – hour x day anomaly rate grid
GET /analytics/trend     – daily time-series (tx count, anomaly rate, etc.)
GET /analytics/model     – current model versions and training metadata
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import ModelVersion, Transaction
from auth.auth import TokenData, get_current_user  # type: ignore[import]

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/heatmap")
async def heatmap(
    chain:  str | None = Query(None),
    metric: str        = Query("anomaly_rate", pattern="^(anomaly_rate|tx_count)$"),
    days:   int        = Query(30, ge=7, le=90),
    db:     AsyncSession = Depends(get_db),
    _:      TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Returns a 7x24 grid (day-of-week x hour-of-day).
    Each cell contains the requested metric averaged over the last `days` days.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    q = select(Transaction).where(Transaction.timestamp >= since)
    if chain:
        q = q.where(Transaction.chain == chain)

    rows = (await db.execute(q)).scalars().all()

    # Bucket into day x hour
    buckets: dict[tuple[int, int], list[float]] = {}
    for tx in rows:
        if not tx.timestamp:
            continue
        key = (tx.timestamp.weekday(), tx.timestamp.hour)
        if key not in buckets:
            buckets[key] = []
        val = float(tx.anomaly_score or 0) if metric == "anomaly_rate" else 1.0
        buckets[key].append(val)

    cells = []
    for day in range(7):
        for hour in range(24):
            vals = buckets.get((day, hour), [])
            value = (sum(vals) / len(vals)) if vals else 0.0
            cells.append({"day": day, "hour": hour, "value": round(value, 4), "count": len(vals)})

    return {"metric": metric, "days": days, "cells": cells}


@router.get("/trend")
async def trend(
    metric: str = Query("tx_count", pattern="^(tx_count|anomaly_rate|flagged_wallets|avg_score)$"),
    days:   int = Query(30, ge=7, le=90),
    chain:  str | None = Query(None),
    db:     AsyncSession = Depends(get_db),
    _:      TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    """Daily aggregated time-series for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    q = select(Transaction).where(Transaction.timestamp >= since)
    if chain:
        q = q.where(Transaction.chain == chain)
    rows = (await db.execute(q)).scalars().all()

    # Group by calendar date
    by_date: dict[str, list[Transaction]] = {}
    for tx in rows:
        if not tx.timestamp:
            continue
        date_key = tx.timestamp.date().isoformat()
        by_date.setdefault(date_key, []).append(tx)

    # Fill every day in range (including days with no data)
    points = []
    for i in range(days):
        date = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        day_txs = by_date.get(date, [])
        scores  = [float(t.anomaly_score or 0) for t in day_txs]
        flagged_wallets = len({t.from_address for t in day_txs if t.flagged})

        points.append({
            "date":            date,
            "tx_count":        len(day_txs),
            "anomaly_rate":    round(sum(1 for t in day_txs if t.flagged) / max(len(day_txs), 1), 4),
            "flagged_wallets": flagged_wallets,
            "avg_score":       round(sum(scores) / max(len(scores), 1), 4),
        })

    return {"metric": metric, "days": days, "points": points}


@router.get("/model")
async def model_stats(
    db: AsyncSession = Depends(get_db),
    _:  TokenData    = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Current and historical model version records."""
    result = await db.execute(
        select(ModelVersion).order_by(desc(ModelVersion.trained_at)).limit(10)
    )
    rows = result.scalars().all()
    return [
        {
            "id":            r.id,
            "model_type":    r.model_type,
            "version":       r.version,
            "training_rows": r.training_rows,
            "labels_used":   r.labels_used,
            "contamination": r.contamination,
            "artifact_path": r.artifact_path,
            "metrics":       r.metrics_json,
            "trained_at":    r.trained_at.isoformat() if r.trained_at else None,
        }
        for r in rows
    ]
