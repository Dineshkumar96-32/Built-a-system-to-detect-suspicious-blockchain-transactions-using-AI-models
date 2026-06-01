"""app/schemas/transactions.py"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             Optional[int]   = None
    tx_hash:        str
    chain:          str
    block_number:   Optional[int]   = None
    from_address:   str
    to_address:     Optional[str]   = None
    value_eth:      float           = 0.0
    gas_price_gwei: Optional[float] = None
    anomaly_score:  Optional[float] = None
    gnn_risk_score: Optional[float] = None
    flagged:        bool            = False
    community_id:   Optional[int]   = None
    features_json:  Optional[Dict[str, Any]] = None
    timestamp:      Optional[datetime] = None
    created_at:     Optional[datetime] = None


class TransactionPage(BaseModel):
    total: int
    page:  int
    size:  int
    items: List[TransactionOut]
