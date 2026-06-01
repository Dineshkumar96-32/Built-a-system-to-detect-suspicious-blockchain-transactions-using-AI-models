"""
app/routes/alerts.py
─────────────────────
Alert management endpoints.

GET    /alerts                 – paginated list with status/severity filters
GET    /alerts/{id}            – single alert with comments
POST   /alerts/{id}/assign     – assign to analyst → status: assigned
POST   /alerts/{id}/comment    – add a comment to the thread
POST   /alerts/{id}/close      – close with structured resolution
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Alert, AlertComment
from auth.auth import TokenData, get_current_user  # type: ignore[import]

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_VALID_RESOLUTIONS = {
    "confirmed_fraud", "false_positive", "escalated", "monitoring"
}


# ── Pydantic bodies ───────────────────────────────────────────

class AssignRequest(BaseModel):
    analyst_id: str


class CommentRequest(BaseModel):
    text: str


class CloseRequest(BaseModel):
    resolution: str
    note:       str = ""


# ── Service helpers (mockable in tests) ───────────────────────

async def list_alerts(
    db: AsyncSession,
    page: int,
    size: int,
    status_filter: str | None,
    severity: str | None,
) -> dict[str, Any]:
    filters = []
    if status_filter:
        filters.append(Alert.status == status_filter)
    if severity:
        filters.append(Alert.severity == severity)

    q = select(Alert).order_by(desc(Alert.created_at))
    if filters:
        q = q.where(and_(*filters))

    rows  = (await db.execute(q.offset((page - 1) * size).limit(size))).scalars().all()
    total = (await db.execute(select(Alert).where(and_(*filters)) if filters else select(Alert))).scalars()
    return {"total": len(list(total)), "page": page, "size": size, "items": [_alert_dict(a) for a in rows]}


async def assign_alert(db: AsyncSession, alert_id: str, analyst_id: str) -> dict[str, Any]:
    alert = await _get_or_404(db, alert_id)
    alert.status      = "assigned"
    alert.assigned_to = analyst_id
    alert.updated_at  = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    return _alert_dict(alert)


async def add_comment(
    db: AsyncSession, alert_id: str, analyst_id: str, text: str
) -> dict[str, Any]:
    await _get_or_404(db, alert_id)
    comment = AlertComment(alert_id=alert_id, analyst_id=analyst_id, text=text)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {
        "id":         comment.id,
        "alert_id":   comment.alert_id,
        "analyst_id": comment.analyst_id,
        "text":       comment.text,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


async def close_alert(
    db: AsyncSession, alert_id: str, resolution: str, note: str
) -> dict[str, Any]:
    alert = await _get_or_404(db, alert_id)
    alert.status          = "closed"
    alert.resolution      = resolution
    alert.resolution_note = note
    alert.resolved_at     = datetime.now(timezone.utc)
    alert.updated_at      = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    return _alert_dict(alert)


# ── Internal helpers ──────────────────────────────────────────

async def _get_or_404(db: AsyncSession, alert_id: str) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id!r} not found")
    return alert


def _alert_dict(a: Alert) -> dict[str, Any]:
    return {
        "id":              a.id,
        "tx_hash":         a.tx_hash,
        "wallet":          a.wallet,
        "chain":           a.chain,
        "severity":        a.severity,
        "status":          a.status,
        "score":           a.score,
        "rule_id":         a.rule_id,
        "assigned_to":     a.assigned_to,
        "resolution":      a.resolution,
        "resolution_note": a.resolution_note,
        "resolved_at":     a.resolved_at.isoformat() if a.resolved_at else None,
        "created_at":      a.created_at.isoformat() if a.created_at else None,
        "updated_at":      a.updated_at.isoformat() if a.updated_at else None,
    }


# ── Routes ────────────────────────────────────────────────────

@router.get("")
async def get_alerts(
    page:     int            = Query(1,    ge=1),
    size:     int            = Query(50,   ge=1, le=200),
    status:   str | None     = Query(None, pattern="^(open|assigned|closed)$"),
    severity: str | None     = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    db:       AsyncSession   = Depends(get_db),
    _:        TokenData      = Depends(get_current_user),
) -> dict[str, Any]:
    return await list_alerts(db, page, size, status, severity)


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    _:  TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    alert = await _get_or_404(db, alert_id)
    data  = _alert_dict(alert)
    # Load comments
    result   = await db.execute(
        select(AlertComment).where(AlertComment.alert_id == alert_id)
    )
    comments = result.scalars().all()
    data["comments"] = [
        {"id": c.id, "analyst_id": c.analyst_id, "text": c.text,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in comments
    ]
    return data


@router.post("/{alert_id}/assign")
async def assign(
    alert_id: str,
    body:     AssignRequest,
    db:       AsyncSession = Depends(get_db),
    _:        TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    return await assign_alert(db, alert_id, body.analyst_id)


@router.post("/{alert_id}/comment")
async def comment(
    alert_id: str,
    body:     CommentRequest,
    db:       AsyncSession = Depends(get_db),
    current:  TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    return await add_comment(db, alert_id, current.sub, body.text)


@router.post("/{alert_id}/close")
async def close(
    alert_id: str,
    body:     CloseRequest,
    db:       AsyncSession = Depends(get_db),
    _:        TokenData    = Depends(get_current_user),
) -> dict[str, Any]:
    if body.resolution not in _VALID_RESOLUTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"resolution must be one of: {sorted(_VALID_RESOLUTIONS)}",
        )
    return await close_alert(db, alert_id, body.resolution, body.note)
