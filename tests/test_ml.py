"""
tests/test_ml.py
Unit tests for the fraud detection ML pipeline.
"""
import pytest
from app.ml.features import extract_features, FEATURE_NAMES
from app.ml.model import FraudDetector
from app.ml.wallet_graph import WalletGraph
from datetime import datetime, timezone


def make_tx(**kwargs):
    base = {
        "hash": "0xabc123",
        "block_number": 19000000,
        "timestamp": datetime.now(timezone.utc),
        "from_address": "0xsender",
        "to_address": "0xreceiver",
        "value_eth": 1.0,
        "gas": 21000,
        "gas_limit": 21000,
        "gas_price_gwei": 30.0,
        "input_data": "0x",
    }
    base.update(kwargs)
    return base


class TestFeatureExtraction:
    def test_feature_count(self):
        tx = make_tx()
        features = extract_features(tx)
        assert len(features) == len(FEATURE_NAMES)

    def test_contract_call_detection(self):
        tx = make_tx(input_data="0x5cffe9de" + "00" * 32)
        features = extract_features(tx)
        assert features["is_contract_call"] == 1.0
        assert features["input_length"] > 2

    def test_normal_tx(self):
        tx = make_tx(input_data="0x")
        features = extract_features(tx)
        assert features["is_contract_call"] == 0.0

    def test_value_log(self):
        import math
        tx = make_tx(value_eth=100.0)
        features = extract_features(tx)
        assert abs(features["value_log"] - math.log1p(100.0)) < 1e-6


class TestFraudDetector:
    @pytest.fixture
    def detector(self):
        d = FraudDetector()
        d._bootstrap_default()
        return d

    def test_normal_tx_low_risk(self, detector):
        tx = make_tx(value_eth=0.1, gas_price_gwei=20.0)
        result = detector.predict(tx)
        assert result["risk_score"] >= 0
        assert result["risk_score"] <= 100
        assert "is_flagged" in result
        assert "signals" in result

    def test_flash_loan_detected(self, detector):
        # Known Aave flash loan signature
        tx = make_tx(
            value_eth=500.0,
            input_data="0x5cffe9de" + "00" * 32,
            gas_price_gwei=200.0,
        )
        result = detector.predict(tx, block_tx_count=80)
        assert result["risk_score"] >= 70.0
        assert result["is_flagged"] is True
        assert any("flash" in s.lower() for s in result["signals"])

    def test_high_value_flagged(self, detector):
        tx = make_tx(value_eth=1000.0)
        result = detector.predict(tx)
        assert result["risk_score"] >= 70.0

    def test_result_structure(self, detector):
        tx = make_tx()
        result = detector.predict(tx)
        for key in ("risk_score", "is_flagged", "fraud_type", "confidence", "signals"):
            assert key in result


class TestWalletGraph:
    def test_add_and_cluster(self):
        graph = WalletGraph()
        wallets = [f"0x{i:040x}" for i in range(10)]

        # Create a ring of transfers
        for i in range(len(wallets)):
            graph.add_transaction(wallets[i], wallets[(i + 1) % len(wallets)], 1.0)

        clusters = graph.detect_clusters(min_cluster_size=3)
        assert len(clusters) > 0

    def test_wallet_stats(self):
        graph = WalletGraph()
        graph.add_transaction("0xaaaa", "0xbbbb", 5.0)
        stats = graph.wallet_stats("0xaaaa")
        assert stats["tx_count"] == 1
        assert abs(stats["volume_eth"] - 5.0) < 0.01

    def test_flag_propagates(self):
        graph = WalletGraph()
        for i in range(5):
            graph.add_transaction("0xbad", f"0x{i:040x}", 1.0)
        graph.flag_address("0xbad")
        stats = graph.wallet_stats("0xbad")
        assert stats["risk_score"] == 100.0
