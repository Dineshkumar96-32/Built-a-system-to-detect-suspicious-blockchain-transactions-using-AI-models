"""app/schemas/transactions.py"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id:             Optional[int]   = None
    hash:           str             = Field(validation_alias="tx_hash")
    chain:          str             = "ethereum"
    block_number:   Optional[int]   = None
    from_address:   str
    to_address:     Optional[str]   = None
    value_eth:      float           = 0.0
    gas_price_gwei: Optional[float] = None
    risk_score:     Optional[float] = Field(validation_alias="anomaly_score", default=0.0)
    gnn_risk_score: Optional[float] = None
    is_flagged:     bool            = Field(validation_alias="flagged", default=False)
    community_id:   Optional[int]   = None
    features_json:  Optional[Dict[str, Any]] = None
    timestamp:      Optional[datetime] = None
    created_at:     Optional[datetime] = None
    fraud_type:     Optional[str]   = None
    confidence:     float           = 0.0
    signals:        List[str]       = []


class TransactionPage(BaseModel):
    total: int
    page:  int
    size:  int
    items: List[TransactionOut]
