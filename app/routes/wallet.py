"""
app/routes/wallet.py
─────────────────────
Wallet endpoints: risk profile, cluster, transaction timeline.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Transaction
from app.schemas.wallet import ClusterOut, WalletRiskOut
from auth.auth import TokenData, get_current_user  # type: ignore[import]

router = APIRouter(prefix="/wallet", tags=["Wallet"])

_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _validate_address(address: str) -> None:
    if not _ADDR_RE.match(address):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid EVM address format: {address!r}",
        )


# ── Mockable service functions ────────────────────────────────

async def compute_wallet_risk(
    address: str, db: AsyncSession, request: Request
) -> dict[str, Any]:
    """Compute or return cached risk profile for a wallet."""
    result = await db.execute(
        select(Transaction)
        .where(or_(Transaction.from_address == address, Transaction.to_address == address))
        .order_by(desc(Transaction.created_at))
        .limit(500)
    )
    txs = result.scalars().all()
    if not txs:
        return {
            "address": address, "anomaly_score": 0.0, "gnn_risk_score": None,
            "ofac_flagged": False, "mixer_interaction": False, "bridge_interaction": False,
            "out_degree": 0, "in_degree": 0, "tx_count_24h": 0,
            "unique_counterparties": 0, "counterparty_entropy": 0.0,
            "community_id": None, "cluster_size": 0, "risk_tier": "LOW", "last_seen": None,
            "risk_score": 0.0, "tx_count": 0, "volume_eth": 0.0, "cluster_risk": 0.0, "known": False,
        }

    scores      = [t.anomaly_score for t in txs if t.anomaly_score is not None]
    avg_score   = sum(scores) / len(scores) if scores else 0.0
    gnn_scores  = [t.gnn_risk_score for t in txs if t.gnn_risk_score is not None]
    gnn_avg     = sum(gnn_scores) / len(gnn_scores) if gnn_scores else None
    out_degree  = sum(1 for t in txs if t.from_address == address)
    in_degree   = len(txs) - out_degree
    last_seen   = max((t.timestamp for t in txs if t.timestamp), default=None)
    feat        = txs[0].features_json or {}
    community   = txs[0].community_id

    risk_tier = (
        "CRITICAL" if avg_score >= 0.85 else
        "HIGH"     if avg_score >= 0.65 else
        "MEDIUM"   if avg_score >= 0.4  else
        "LOW"
    )

    from app.ml.wallet_graph import get_wallet_graph
    graph = get_wallet_graph()
    cluster_risk = graph.cluster_risk_score(address)

    return {
        "address":              address,
        "anomaly_score":        round(avg_score, 4),
        "gnn_risk_score":       round(gnn_avg, 4) if gnn_avg else None,
        "ofac_flagged":         bool(feat.get("ofac_flagged", 0)),
        "mixer_interaction":    bool(feat.get("mixer_interaction", 0)),
        "bridge_interaction":   bool(feat.get("bridge_interaction", 0)),
        "out_degree":           out_degree,
        "in_degree":            in_degree,
        "tx_count_24h":         int(feat.get("tx_24h", 0)),
        "unique_counterparties":int(feat.get("unique_counterparties", 0)),
        "counterparty_entropy": round(float(feat.get("counterparty_entropy", 0.0)), 4),
        "community_id":         community,
        "cluster_size":         0,   # populated by cluster endpoint
        "risk_tier":            risk_tier,
        "last_seen":            last_seen.isoformat() if last_seen else None,
        "risk_score":           round(avg_score * 100, 2),
        "tx_count":             len(txs),
        "volume_eth":           round(sum(float(t.value_eth or 0) for t in txs), 4),
        "cluster_risk":         cluster_risk,
        "known":                True,
    }


async def get_wallet_cluster(
    address: str, db: AsyncSession
) -> dict[str, Any]:
    result = await db.execute(
        select(Transaction).where(Transaction.from_address == address).limit(1)
    )
    tx = result.scalar_one_or_none()
    community_id = tx.community_id if tx else None

    if community_id is None:
        return {"community_id": None, "nodes": [], "edges": []}

    cluster_txs_q = await db.execute(
        select(Transaction).where(Transaction.community_id == community_id).limit(200)
    )
    cluster_txs = cluster_txs_q.scalars().all()

    wallets: set[str] = set()
    edges: list[dict[str, Any]] = []
    for t in cluster_txs:
        wallets.add(t.from_address)
        if t.to_address:
            wallets.add(t.to_address)
            edges.append({
                "from": t.from_address,
                "to":   t.to_address,
                "tx_count": 1,
                "total_eth": float(t.value_eth or 0),
            })

    nodes = [{"address": w, "risk_tier": "UNKNOWN", "gnn_risk_score": None} for w in wallets]
    return {"community_id": community_id, "nodes": nodes, "edges": edges}


async def get_wallet_timeline(
    address: str,
    db: AsyncSession,
    limit: int = 100,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Transaction)
        .where(or_(Transaction.from_address == address, Transaction.to_address == address))
        .order_by(desc(Transaction.timestamp))
        .limit(limit)
    )
    txs = result.scalars().all()
    return [
        {
            "tx_hash":       t.tx_hash,
            "chain":         t.chain,
            "direction":     "sent" if t.from_address == address else "received",
            "counterparty":  t.to_address if t.from_address == address else t.from_address,
            "value_eth":     float(t.value_eth or 0),
            "gas_price_gwei":float(t.gas_price_gwei or 0),
            "anomaly_score": t.anomaly_score,
            "flagged":       t.flagged,
            "timestamp":     t.timestamp.isoformat() if t.timestamp else None,
        }
        for t in txs
    ]


# ── Routes ────────────────────────────────────────────────────

@router.get("/{address}/risk")
async def wallet_risk(
    address: str,
    request: Request,
    db: AsyncSession  = Depends(get_db),
    _:  TokenData     = Depends(get_current_user),
) -> dict[str, Any]:
    _validate_address(address)
    return await compute_wallet_risk(address, db, request)


@router.get("/{address}/cluster", response_model=ClusterOut)
async def wallet_cluster(
    address: str,
    db: AsyncSession = Depends(get_db),
    _:  TokenData    = Depends(get_current_user),
) -> ClusterOut:
    _validate_address(address)
    data = await get_wallet_cluster(address, db)
    return ClusterOut(**data)


@router.get("/{address}/timeline")
async def wallet_timeline(
    address: str,
    limit: int        = Query(100, ge=1, le=500),
    db: AsyncSession  = Depends(get_db),
    _:  TokenData     = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _validate_address(address)
    return await get_wallet_timeline(address, db, limit)


# Create a new router for plural "/wallets" endpoints
wallets_router = APIRouter(prefix="/wallets", tags=["Wallets"])

@wallets_router.get("/top-risk")
async def top_risk_wallets(
    n: int = Query(20, ge=1, le=100),
    _: TokenData = Depends(get_current_user),
) -> list[dict[str, Any]]:
    from app.ml.wallet_graph import get_wallet_graph
    graph = get_wallet_graph()
    stats = graph.top_risky_wallets(n=n)
    return [
        {
            "address": w.get("address"),
            "tx_count": w.get("tx_count", 0),
            "volume_eth": w.get("volume_eth", 0.0),
            "risk_score": w.get("risk_score", 0.0),
            "cluster_id": w.get("cluster_id"),
            "cluster_risk": w.get("cluster_risk", 0.0),
            "out_degree": w.get("out_degree", 0),
            "in_degree": w.get("in_degree", 0),
            "known": True
        }
        for w in stats
    ]

@wallets_router.get("/graph")
async def wallet_network_graph(
    limit: int = Query(150, ge=1, le=500),
    _: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    from app.ml.wallet_graph import get_wallet_graph
    graph = get_wallet_graph()
    return graph.to_dict(max_nodes=limit)
