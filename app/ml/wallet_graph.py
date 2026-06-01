"""
app/ml/wallet_graph.py
Graph-based wallet clustering using NetworkX.

Builds a directed transaction graph where:
  - Nodes = wallet addresses
  - Edges = ETH transfer (weight = value_eth)

Applies Louvain-style community detection to identify
coordinated wallet groups (mixers, wash traders, etc.).
"""

from __future__ import annotations
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import networkx as nx
from app.core.logger import get_logger

logger = get_logger("blockshield.wallet_graph")

# Minimum ETH on an edge to be included in clustering
EDGE_WEIGHT_THRESHOLD = 0.01


class WalletGraph:
    """
    Incremental transaction graph + clustering engine.

    Usage:
        graph = WalletGraph()
        graph.add_transaction(from_addr, to_addr, value_eth)
        clusters = graph.detect_clusters()
        risk = graph.cluster_risk_score(address)
    """

    def __init__(self):
        self._G = nx.DiGraph()
        self._cluster_map: Dict[str, int] = {}      # address → cluster_id
        self._cluster_risk: Dict[int, float] = {}   # cluster_id → risk score
        self._flagged_addresses: set[str] = set()
        self._dirty = False     # True when graph has changed since last cluster run

    # ── Graph construction ────────────────────────────────────────────────────

    def add_transaction(
        self,
        from_addr: str,
        to_addr: Optional[str],
        value_eth: float,
        risk_score: float = 0.0,
    ) -> None:
        if not to_addr or value_eth < EDGE_WEIGHT_THRESHOLD:
            return

        from_addr = from_addr.lower()
        to_addr = to_addr.lower()

        # Update node attributes
        for addr in (from_addr, to_addr):
            if addr not in self._G:
                self._G.add_node(addr, risk_score=0.0, tx_count=0, volume=0.0)

        self._G.nodes[from_addr]["tx_count"] = self._G.nodes[from_addr].get("tx_count", 0) + 1
        self._G.nodes[from_addr]["volume"] = self._G.nodes[from_addr].get("volume", 0.0) + value_eth

        if risk_score > 0:
            prev = self._G.nodes[from_addr].get("risk_score", 0.0)
            self._G.nodes[from_addr]["risk_score"] = max(prev, risk_score)

        # Update / create edge
        if self._G.has_edge(from_addr, to_addr):
            self._G[from_addr][to_addr]["weight"] += value_eth
            self._G[from_addr][to_addr]["tx_count"] += 1
        else:
            self._G.add_edge(from_addr, to_addr, weight=value_eth, tx_count=1)

        self._dirty = True

    def flag_address(self, address: str) -> None:
        self._flagged_addresses.add(address.lower())
        if address.lower() in self._G:
            self._G.nodes[address.lower()]["risk_score"] = 100.0

    # ── Clustering ────────────────────────────────────────────────────────────

    def detect_clusters(self, min_cluster_size: int = 3) -> Dict[str, int]:
        """
        Run community detection on the undirected projection.
        Returns mapping of address → cluster_id.

        Uses greedy modularity maximisation (NetworkX built-in).
        For large graphs, this can be swapped for python-louvain.
        """
        if not self._dirty and self._cluster_map:
            return self._cluster_map

        if len(self._G) < min_cluster_size:
            return {}

        # Work on undirected version for community detection
        UG = self._G.to_undirected()

        try:
            communities = nx.community.greedy_modularity_communities(UG, weight="weight")
        except Exception as exc:
            logger.warning("Clustering failed", error=str(exc))
            return {}

        self._cluster_map = {}
        self._cluster_risk = {}

        for cluster_id, community in enumerate(communities):
            if len(community) < min_cluster_size:
                continue
            for addr in community:
                self._cluster_map[addr] = cluster_id

            # Cluster risk = max node risk within community
            node_risks = [
                self._G.nodes[addr].get("risk_score", 0.0) for addr in community
            ]
            flagged_ratio = sum(
                1 for addr in community if addr in self._flagged_addresses
            ) / len(community)

            cluster_risk = max(node_risks) * 0.6 + flagged_ratio * 100 * 0.4
            self._cluster_risk[cluster_id] = round(cluster_risk, 2)

        self._dirty = False
        logger.info(
            "Clusters detected",
            clusters=len(self._cluster_risk),
            nodes=len(self._G),
        )
        return self._cluster_map

    # ── Query helpers ─────────────────────────────────────────────────────────

    def cluster_risk_score(self, address: str) -> float:
        """Return the risk score of the cluster containing this address."""
        address = address.lower()
        cluster_id = self._cluster_map.get(address)
        if cluster_id is None:
            return 0.0
        return self._cluster_risk.get(cluster_id, 0.0)

    def get_cluster_members(self, address: str) -> List[str]:
        """Return all wallets in the same cluster as `address`."""
        address = address.lower()
        cluster_id = self._cluster_map.get(address)
        if cluster_id is None:
            return []
        return [a for a, c in self._cluster_map.items() if c == cluster_id]

    def wallet_stats(self, address: str) -> Dict:
        address = address.lower()
        if address not in self._G:
            return {}
        node = self._G.nodes[address]
        return {
            "address": address,
            "tx_count": node.get("tx_count", 0),
            "volume_eth": round(node.get("volume", 0.0), 4),
            "risk_score": node.get("risk_score", 0.0),
            "cluster_id": self._cluster_map.get(address),
            "cluster_risk": self.cluster_risk_score(address),
            "out_degree": self._G.out_degree(address),
            "in_degree": self._G.in_degree(address),
        }

    def top_risky_wallets(self, n: int = 20) -> List[Dict]:
        wallets = [
            self.wallet_stats(addr)
            for addr in self._G.nodes
        ]
        return sorted(wallets, key=lambda w: w.get("risk_score", 0), reverse=True)[:n]

    @property
    def node_count(self) -> int:
        return len(self._G)

    @property
    def edge_count(self) -> int:
        return len(self._G.edges)

    def to_dict(self, max_nodes: int = 200) -> Dict:
        """Export the graph for visualization (nodes/links format)."""
        # Take the top N nodes by tx_count/volume to keep the graph readable
        sorted_nodes = sorted(
            self._G.nodes, 
            key=lambda n: self._G.nodes[n].get("tx_count", 0), 
            reverse=True
        )[:max_nodes]
        
        nodes_set = set(sorted_nodes)
        
        nodes = []
        for addr in sorted_nodes:
            stats = self.wallet_stats(addr)
            nodes.append({
                "id": addr,
                "address": addr,
                "risk": stats["risk_score"],
                "val": math.log10(stats["tx_count"] + 1) * 2, # for node size
                "group": stats["cluster_id"] if stats["cluster_id"] is not None else -1
            })
            
        links = []
        for u, v, data in self._G.edges(data=True):
            if u in nodes_set and v in nodes_set:
                links.append({
                    "source": u,
                    "target": v,
                    "value": data.get("weight", 0)
                })
                
        return {"nodes": nodes, "links": links}


# ── Module-level singleton ────────────────────────────────────────────────────
_wallet_graph: WalletGraph | None = None


def get_wallet_graph() -> WalletGraph:
    global _wallet_graph
    if _wallet_graph is None:
        _wallet_graph = WalletGraph()
    return _wallet_graph
