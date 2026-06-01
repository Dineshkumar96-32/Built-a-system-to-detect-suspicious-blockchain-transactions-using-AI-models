"""
app/api/alerts.py
"""
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from datetime import datetime

from app.blockchain.pipeline import get_recent_alerts

router = APIRouter()


class AlertOut(BaseModel):
    id: str
    tx_hash: str
    alert_type: str
    severity: str
    risk_score: float
    description: str
    wallet_address: Optional[str]
    value_eth: float
    created_at: str
    resolved: bool


@router.get("/alerts", response_model=List[AlertOut])
async def list_alerts(
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    unresolved_only: bool = Query(True),
):
    alerts = get_recent_alerts(limit=100)
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    if unresolved_only:
        alerts = [a for a in alerts if not a.get("resolved")]
    return alerts[:limit]
