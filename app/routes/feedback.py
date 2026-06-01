"""
app/routes/feedback.py
───────────────────────
Analyst feedback endpoints.

POST /feedback         – submit label (0=safe, 1=risky)
GET  /feedback/stats   – pending count and retrain threshold
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import AnalystFeedback
from auth.auth import TokenData, get_current_user  # type: ignore[import]

router = APIRouter(prefix="/feedback", tags=["Feedback"])

import os
_RETRAIN_THRESHOLD = int(os.getenv("RETRAIN_THRESHOLD", "50"))


class FeedbackRequest(BaseModel):
    tx_hash:        str
    wallet_address: str
    label:          int = Field(..., ge=0, le=1)   # 0=safe, 1=risky
    features:       dict = {}


async def record_feedback(
    db: AsyncSession, req: FeedbackRequest, analyst_id: str
) -> dict[str, Any]:
    # Check for duplicate
    from sqlalchemy import select
    existing = (
        await db.execute(select(AnalystFeedback).where(AnalystFeedback.tx_hash == req.tx_hash))
    ).scalar_one_or_none()

    if existing:
        existing.label = req.label
        existing.analyst_id = analyst_id
        existing.features = req.features or existing.features
    else:
        fb = AnalystFeedback(
            tx_hash=req.tx_hash,
            wallet_address=req.wallet_address,
            label=req.label,
            analyst_id=analyst_id,
            features=req.features or None,
        )
        db.add(fb)

    await db.commit()

    # Count pending
    from sqlalchemy import func, select as sel
    count_q = await db.execute(
        sel(func.count()).select_from(AnalystFeedback).where(
            AnalystFeedback.retrain_used.is_(False)
        )
    )
    pending = count_q.scalar() or 0
    return {"status": "accepted", "pending": pending, "retrain_threshold": _RETRAIN_THRESHOLD}


async def get_feedback_stats(db: AsyncSession) -> dict[str, Any]:
    from sqlalchemy import func, select as sel
    pending_q = await db.execute(
        sel(func.count()).select_from(AnalystFeedback).where(
            AnalystFeedback.retrain_used.is_(False)
        )
    )
    total_q = await db.execute(sel(func.count()).select_from(AnalystFeedback))
    return {
        "pending_labels":    pending_q.scalar() or 0,
        "total_labels":      total_q.scalar() or 0,
        "retrain_threshold": _RETRAIN_THRESHOLD,
    }


@router.post("")
async def submit_feedback(
    req:     FeedbackRequest,
    db:      AsyncSession = Depends(get_db),
    current: TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    return await record_feedback(db, req, current.sub)


@router.get("/stats")
async def feedback_stats(
    db: AsyncSession = Depends(get_db),
    _:  TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_feedback_stats(db)
