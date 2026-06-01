"""
app/api/transactions.py
REST endpoints for transaction data.
"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from ..blockchain.pipeline import get_recent_transactions
from ..ml.model import get_detector
from ..core.database import get_db
from ..models import Transaction

router = APIRouter()


class TransactionOut(BaseModel):
    hash: str
    block_number: int
    timestamp: datetime
    from_address: str
    to_address: Optional[str]
    value_eth: float
    gas_price_gwei: float
    risk_score: float
    is_flagged: bool
    fraud_type: Optional[str]
    confidence: float
    signals: List[str] = []

    class Config:
        from_attributes = True


@router.get("/transactions", response_model=List[TransactionOut])
async def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    flagged_only: bool = Query(False),
    min_risk: float = Query(0.0, ge=0, le=100),
):
    """
    Return recent transactions from the in-memory buffer.
    Filter by flagged status or minimum risk score.
    """
    txs = get_recent_transactions(limit=200)

    if flagged_only:
        txs = [t for t in txs if t.get("is_flagged")]

    if min_risk > 0:
        txs = [t for t in txs if t.get("risk_score", 0) >= min_risk]

    return txs[:limit]


@router.get("/transactions/{tx_hash}", response_model=TransactionOut)
async def get_transaction(tx_hash: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a specific transaction by hash.
    Searches the in-memory buffer first, then falls back to the database.
    """
    # 1. Check Buffer
    txs = get_recent_transactions(limit=1000)
    for tx in txs:
        if tx.get("hash", "").lower() == tx_hash.lower():
            return tx
    
    # 2. Check Database
    stmt = select(Transaction).where(Transaction.tx_hash == tx_hash)
    result = await db.execute(stmt)
    tx_record = result.scalar_one_or_none()
    
    if tx_record:
        return {
            "hash": tx_record.tx_hash,
            "block_number": tx_record.block_number,
            "timestamp": tx_record.timestamp,
            "from_address": tx_record.from_address,
            "to_address": tx_record.to_address,
            "value_eth": float(tx_record.value_eth) if tx_record.value_eth else 0.0,
            "gas_price_gwei": float(tx_record.gas_price_gwei) if tx_record.gas_price_gwei else 0.0,
            "risk_score": tx_record.anomaly_score or 0.0,
            "is_flagged": tx_record.flagged,
            "fraud_type": None,
            "confidence": 0.0,
            "signals": []
        }

    raise HTTPException(status_code=404, detail="Transaction not found")


@router.get("/search", response_model=List[TransactionOut])
async def search_transactions(q: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    """
    Search transactions by hash, from_address, or to_address.
    Checks buffer first, then database for historical records.
    """
    # 1. Check Buffer
    txs = get_recent_transactions(limit=1000)
    q_lower = q.lower()
    results = []
    seen_hashes = set()
    
    for tx in txs:
        h = tx.get("hash", "").lower()
        if (q_lower in h or
            q_lower in tx.get("from_address", "").lower() or
            q_lower in str(tx.get("to_address", "")).lower()):
            results.append(tx)
            seen_hashes.add(h)
    
    # 2. Check Database for more results
    if len(results) < 50:
        stmt = select(Transaction).where(
            or_(
                Transaction.tx_hash.ilike(f"%{q}%"),
                Transaction.from_address.ilike(f"%{q}%"),
                Transaction.to_address.ilike(f"%{q}%")
            )
        ).limit(50 - len(results))
        
        db_result = await db.execute(stmt)
        for record in db_result.scalars():
            if record.tx_hash.lower() not in seen_hashes:
                results.append({
                    "hash": record.tx_hash,
                    "block_number": record.block_number,
                    "timestamp": record.timestamp,
                    "from_address": record.from_address,
                    "to_address": record.to_address,
                    "value_eth": float(record.value_eth) if record.value_eth else 0.0,
                    "gas_price_gwei": float(record.gas_price_gwei) if record.gas_price_gwei else 0.0,
                    "risk_score": record.anomaly_score or 0.0,
                    "is_flagged": record.flagged,
                    "fraud_type": None,
                    "confidence": 0.0,
                    "signals": []
                })
                
    return results[:50]


@router.post("/transactions/analyze")
async def analyze_transaction(tx: dict):
    """
    On-demand analysis of a transaction dict.
    Useful for testing or manual analysis.
    """
    detector = get_detector()
    result = detector.predict(tx)
    return {**tx, **result}
