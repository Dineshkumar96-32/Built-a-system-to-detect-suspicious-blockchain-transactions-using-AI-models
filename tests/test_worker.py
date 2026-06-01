"""
tests/pipeline/test_worker.py
──────────────────────────────
Unit tests for the PipelineWorker processing logic.

Each method is tested in isolation using mocks.
No real broker, DB, or chain connection required.

Run:
    pytest tests/pipeline/test_worker.py -v
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.worker import PipelineWorker


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def worker() -> PipelineWorker:
    w = PipelineWorker()
    # Inject mock dependencies
    w._broker      = MagicMock()
    w._live_model  = MagicMock()
    w._engineer    = MagicMock()
    w._running     = True
    return w


SAMPLE_TX = {
    "hash":        "0x" + "d" * 64,
    "chain":       "ethereum",
    "from":        "0x" + "a" * 40,
    "to":          "0x" + "b" * 40,
    "value":       "0xDE0B6B3A7640000",   # 1 ETH
    "gas":         "0x5208",
    "gasPrice":    "0x9502F900",
    "blockNumber": "0x12D687",
}

SAMPLE_FEATURES = {
    "anomaly_score": 0.0,  # will be overridden
    "gas_price_gwei": 4.0,
    "out_degree": 5.0,
    "in_degree": 2.0,
    "tx_count_24h": 3.0,
    "ofac_flagged": 0.0,
    "mixer_interaction": 0.0,
}


# ─────────────────────────────────────────────────────────────
# Rule evaluation
# ─────────────────────────────────────────────────────────────

class TestRuleEvaluation:
    def test_single_condition_gt_match(self, worker):
        rule = {"groups": [{"logic": "AND", "conditions": [
            {"field": "anomaly_score", "operator": ">", "value": "0.7"}
        ]}]}
        assert worker._rule_matches(rule, {"anomaly_score": 0.9}) is True

    def test_single_condition_gt_no_match(self, worker):
        rule = {"groups": [{"logic": "AND", "conditions": [
            {"field": "anomaly_score", "operator": ">", "value": "0.7"}
        ]}]}
        assert worker._rule_matches(rule, {"anomaly_score": 0.5}) is False

    def test_and_logic_all_must_pass(self, worker):
        rule = {"groups": [{"logic": "AND", "conditions": [
            {"field": "anomaly_score",    "operator": ">",  "value": "0.7"},
            {"field": "mixer_interaction","operator": "==", "value": "1"},
        ]}]}
        # Both true
        assert worker._rule_matches(rule, {"anomaly_score": 0.9, "mixer_interaction": 1.0}) is True
        # Only first true
        assert worker._rule_matches(rule, {"anomaly_score": 0.9, "mixer_interaction": 0.0}) is False

    def test_or_logic_any_passes(self, worker):
        rule = {"groups": [{"logic": "OR", "conditions": [
            {"field": "anomaly_score",    "operator": ">",  "value": "0.95"},
            {"field": "ofac_flagged",     "operator": "==", "value": "1"},
        ]}]}
        # Only OFAC true
        assert worker._rule_matches(rule, {"anomaly_score": 0.5, "ofac_flagged": 1.0}) is True
        # Neither true
        assert worker._rule_matches(rule, {"anomaly_score": 0.5, "ofac_flagged": 0.0}) is False

    def test_multiple_groups_are_ored(self, worker):
        rule = {"groups": [
            {"logic": "AND", "conditions": [{"field": "anomaly_score", "operator": ">", "value": "0.95"}]},
            {"logic": "AND", "conditions": [{"field": "ofac_flagged",  "operator": "==","value": "1"}]},
        ]}
        # First group fails, second passes
        assert worker._rule_matches(rule, {"anomaly_score": 0.5, "ofac_flagged": 1.0}) is True

    def test_empty_rule_no_match(self, worker):
        assert worker._rule_matches({"groups": []}, {"anomaly_score": 0.99}) is False

    def test_missing_field_treated_as_zero(self, worker):
        rule = {"groups": [{"logic": "AND", "conditions": [
            {"field": "nonexistent_field", "operator": ">", "value": "0.5"}
        ]}]}
        assert worker._rule_matches(rule, {}) is False

    @pytest.mark.parametrize("op,val,actual,expected", [
        (">",  "0.5", 0.6, True),
        (">=", "0.5", 0.5, True),
        ("<",  "0.5", 0.4, True),
        ("<=", "0.5", 0.5, True),
        ("==", "1.0", 1.0, True),
        ("!=", "0.0", 1.0, True),
        (">",  "0.5", 0.5, False),
    ])
    def test_operator_coverage(self, worker, op, val, actual, expected):
        rule = {"groups": [{"logic": "AND", "conditions": [
            {"field": "x", "operator": op, "value": val}
        ]}]}
        assert worker._rule_matches(rule, {"x": actual}) is expected

    def test_malformed_rule_does_not_raise(self, worker):
        # Should return False, never raise
        assert worker._rule_matches(None, {}) is False
        assert worker._rule_matches({"groups": None}, {}) is False
        assert worker._rule_matches({"groups": [{"logic": "AND", "conditions": [{"field": None}]}]}, {}) is False


# ─────────────────────────────────────────────────────────────
# _process integration (mocked dependencies)
# ─────────────────────────────────────────────────────────────

class TestProcess:
    @pytest.mark.asyncio
    async def test_process_normal_tx_not_flagged(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.2))  # 0.2 = low risk
        worker._broker.publish = AsyncMock()

        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=[]):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX})

        worker._broker.publish.assert_not_called()  # no alerts published

    @pytest.mark.asyncio
    async def test_process_flagged_tx_publishes_alert(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.91))  # high risk

        mock_alert = {"rule_id": "r1", "severity": "HIGH", "tx_hash": SAMPLE_TX["hash"]}
        worker._broker.publish = AsyncMock()

        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=[mock_alert]):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX})

        worker._broker.publish.assert_called_once()
        call_args = worker._broker.publish.call_args
        assert call_args[0][0] == "alerts"

    @pytest.mark.asyncio
    async def test_process_model_not_loaded_does_not_crash(self, worker):
        """If the model isn't loaded yet, processing should continue with score=0."""
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(side_effect=RuntimeError("Model not loaded"))
        worker._broker.publish = AsyncMock()

        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=[]):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX})   # should not raise

    @pytest.mark.asyncio
    async def test_process_feature_engineer_error_propagates(self, worker):
        worker._engineer.build_features = AsyncMock(side_effect=ConnectionError("RPC down"))
        with pytest.raises(ConnectionError):
            await worker._process({**SAMPLE_TX})

    @pytest.mark.asyncio
    async def test_process_persist_called_once(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.5))
        worker._broker.publish = AsyncMock()

        persist_mock = AsyncMock()
        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=[]):
            with patch.object(worker, "_persist_transaction", persist_mock):
                await worker._process({**SAMPLE_TX})

        persist_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_multiple_alerts_all_published(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.95))
        worker._broker.publish = AsyncMock()

        alerts = [
            {"rule_id": "r1", "severity": "HIGH"},
            {"rule_id": "r2", "severity": "CRITICAL"},
        ]
        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=alerts):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX})

        assert worker._broker.publish.call_count == 2


# ─────────────────────────────────────────────────────────────
# Feature flow
# ─────────────────────────────────────────────────────────────

class TestFeatureFlow:
    @pytest.mark.asyncio
    async def test_engineer_called_with_correct_address(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.3))
        worker._broker.publish = AsyncMock()

        with patch.object(worker, "_evaluate_rules", new_callable=AsyncMock, return_value=[]):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX, "from": "0x" + "c" * 40})

        call_kwargs = worker._engineer.build_features.call_args
        assert call_kwargs[1]["wallet_address"] == "0x" + "c" * 40

    @pytest.mark.asyncio
    async def test_anomaly_score_passed_to_rules(self, worker):
        worker._engineer.build_features = AsyncMock(return_value=SAMPLE_FEATURES)
        worker._live_model.predict = MagicMock(return_value=(-1, 0.88))
        worker._broker.publish = AsyncMock()

        rule_mock = AsyncMock(return_value=[])
        with patch.object(worker, "_evaluate_rules", rule_mock):
            with patch.object(worker, "_persist_transaction", new_callable=AsyncMock):
                await worker._process({**SAMPLE_TX})

        _, _, score = rule_mock.call_args[0]
        assert score == pytest.approx(0.88)
