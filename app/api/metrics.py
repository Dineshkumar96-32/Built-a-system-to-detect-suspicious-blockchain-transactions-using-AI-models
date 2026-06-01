"""
app/api/metrics.py
"""
from fastapi import APIRouter
from app.blockchain.pipeline import get_metrics

router = APIRouter()


@router.get("/metrics")
async def system_metrics():
    """
    Real-time system performance metrics.
    Includes ML model stats, throughput, and detection counts.
    """
    return get_metrics()
