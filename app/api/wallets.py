"""
app/api/wallets.py
"""
from fastapi import APIRouter, HTTPException
from app.ml.wallet_graph import get_wallet_graph

router = APIRouter()


@router.get("/wallet/{address}/risk")
async def wallet_risk(address: str):
    graph = get_wallet_graph()
    stats = graph.wallet_stats(address)
    if not stats:
        return {
            "address": address,
            "risk_score": 0.0,
            "cluster_id": None,
            "cluster_risk": 0.0,
            "tx_count": 0,
            "volume_eth": 0.0,
            "known": False,
        }
    cluster_members = graph.get_cluster_members(address)
    return {**stats, "cluster_members": cluster_members[:10], "known": True}


@router.get("/wallet/{address}/cluster")
async def wallet_cluster(address: str):
    graph = get_wallet_graph()
    members = graph.get_cluster_members(address)
    if not members:
        raise HTTPException(status_code=404, detail="Wallet not in any cluster")
    return {
        "address": address,
        "cluster_id": graph.wallet_stats(address).get("cluster_id"),
        "cluster_risk": graph.cluster_risk_score(address),
        "members": members,
        "member_count": len(members),
    }


@router.get("/wallets/top-risk")
async def top_risk_wallets(n: int = 20):
    graph = get_wallet_graph()
    return graph.top_risky_wallets(n=n)


@router.get("/wallets/graph")
async def wallet_network_graph(limit: int = 150):
    graph = get_wallet_graph()
    return graph.to_dict(max_nodes=limit)
