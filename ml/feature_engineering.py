from typing import Any, Dict

# Reuse the existing robust feature extraction from the main application
from app.ml.features import extract_features

class FeatureEngineer:
    """
    Feature engineering adapter for the background worker pipeline.
    Reuses the core logic from app.ml.features but provides the 
    interface expected by app.worker.
    """
    
    async def load_ofac_list(self) -> None:
        """
        Stub to satisfy worker.py interface. 
        In a full implementation, this would load sanctioned addresses.
        """
        pass

    async def build_features(self, wallet_address: str, transactions: list[Dict[str, Any]]) -> Dict[str, float]:
        """
        Build a feature vector for a transaction.
        
        Args:
            wallet_address: the from address
            transactions: list containing the transaction(s) to process
            
        Returns:
            A dictionary mapping feature names to their float values.
        """
        if not transactions:
            return {}
            
        tx = transactions[0]
        
        # We reuse extract_features which handles gas normalization, eth value, etc.
        # It requires a block_tx_count, we default to 1 if unknown.
        extracted = extract_features(tx, block_tx_count=1, wallet_profile=None)
        
        # The worker explicitly uses 'avg_gas_price' in some places
        extracted["avg_gas_price"] = extracted.get("gas_price_gwei", 30.0)
        
        return extracted
