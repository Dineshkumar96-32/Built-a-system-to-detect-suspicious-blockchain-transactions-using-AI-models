"""
app/ml/features.py
Feature extraction from raw Ethereum transaction data.

Features used by the fraud detection model:
  - value_eth           : ETH transferred
  - gas_price_gwei      : gas price (proxy for urgency / MEV)
  - gas_used_ratio      : gas / gas_limit (efficiency signal)
  - input_length        : length of calldata (contract interaction)
  - is_contract_call    : bool — calldata present
  - hour_of_day         : 0–23 (temporal pattern)
  - day_of_week         : 0–6
  - value_log           : log1p(value_eth) — normalise skew
  - gas_price_log       : log1p(gas_price_gwei)
  - same_block_count    : # txs in same block (flash loan proxy)
  - wallet_tx_count     : historical tx count for sender
  - wallet_avg_value    : historical average tx value for sender
  - wallet_risk_history : sender's running risk score
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any


def extract_features(
    tx: Dict[str, Any],
    block_tx_count: int = 1,
    wallet_profile: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    """
    Convert a raw transaction dict into a flat numeric feature vector.

    Args:
        tx: Raw transaction fields (hash, value_eth, gas, gas_price_gwei, etc.)
        block_tx_count: Number of transactions in the same block (flash loan signal)
        wallet_profile: Historical stats for the sender wallet

    Returns:
        Dict[str, float] — ordered feature dict compatible with the model.
    """
    profile = wallet_profile or {}
    ts: datetime = tx.get("timestamp", datetime.now(timezone.utc))

    value_eth: float = float(tx.get("value_eth", 0.0))
    gas: int = int(tx.get("gas", 21000))
    gas_price_gwei: float = float(tx.get("gas_price_gwei", 0.0))
    input_data: str = tx.get("input_data", "") or ""

    return {
        "value_eth": value_eth,
        "gas_price_gwei": gas_price_gwei,
        "gas_used_ratio": min(gas / max(tx.get("gas_limit", gas), 1), 1.0),
        "input_length": len(input_data),
        "is_contract_call": float(len(input_data) > 2),
        "hour_of_day": float(ts.hour),
        "day_of_week": float(ts.weekday()),
        "value_log": math.log1p(value_eth),
        "gas_price_log": math.log1p(gas_price_gwei),
        "same_block_count": float(block_tx_count),
        "wallet_tx_count": float(profile.get("tx_count", 0)),
        "wallet_avg_value": float(profile.get("avg_tx_value", 0.0)),
        "wallet_risk_history": float(profile.get("risk_score", 0.0)),
    }


FEATURE_NAMES = list(extract_features({}).keys())
