"""app/schemas/wallet.py"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ClusterNode(BaseModel):
    address:        str
    risk_tier:      str
    gnn_risk_score: Optional[float] = None
    tx_count:       int = 0


class ClusterEdge(BaseModel):
    source:    str = ""
    target:    str = ""
    tx_count:  int = 0
    total_eth: float = 0.0


class ClusterOut(BaseModel):
    community_id: Optional[int]
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []


class WalletRiskOut(BaseModel):
    address:              str
    anomaly_score:        float
    gnn_risk_score:       Optional[float]
    ofac_flagged:         bool
    mixer_interaction:    bool
    bridge_interaction:   bool
    out_degree:           int
    in_degree:            int
    tx_count_24h:         int
    unique_counterparties:int
    counterparty_entropy: float
    community_id:         Optional[int]
    cluster_size:         int
    risk_tier:            str
    last_seen:            Optional[str]
