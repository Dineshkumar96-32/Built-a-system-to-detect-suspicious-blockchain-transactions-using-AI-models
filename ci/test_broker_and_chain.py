"""
backend/tests/test_broker_and_chain.py
────────────────────────────────────────
Unit tests for the message broker (all backends) and ChainProvider / ChainRegistry.

Run:
  pytest backend/tests/test_broker_and_chain.py -v
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from broker.message_broker import (  # type: ignore
    BrokerMessage, MemoryBroker, get_broker, reset_broker,
)
from broker.multichain_provider import CHAINS, ChainProvider, ChainRegistry  # type: ignore


# ─────────────────────────────────────────────────────────────
# BrokerMessage
# ─────────────────────────────────────────────────────────────

class TestBrokerMessage:
    def test_roundtrip_json(self):
        msg = BrokerMessage(payload={"tx": "0xabc", "score": 0.9}, topic="transactions")
        restored = BrokerMessage.from_json(msg.to_json())
        assert restored.payload == msg.payload
        assert restored.topic == msg.topic
        assert restored.message_id == msg.message_id

    def test_auto_id_generated(self):
        m1 = BrokerMessage(payload={})
        m2 = BrokerMessage(payload={})
        assert m1.message_id != m2.message_id

    def test_timestamp_set(self):
        m = BrokerMessage(payload={})
        assert "T" in m.timestamp  # ISO8601


# ─────────────────────────────────────────────────────────────
# MemoryBroker
# ─────────────────────────────────────────────────────────────

class TestMemoryBroker:
    @pytest.mark.asyncio
    async def test_connect_close(self):
        b = MemoryBroker()
        await b.connect()
        await b.close()

    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        b = MemoryBroker()
        await b.connect()
        msg = BrokerMessage(payload={"test": True})
        await b.publish("test-topic", msg)

        received = []
        async def consume():
            async for m in b.subscribe("test-topic"):
                received.append(m)
                break  # stop after first

        await asyncio.wait_for(consume(), timeout=2.0)
        assert len(received) == 1
        assert received[0].payload["test"] is True

    @pytest.mark.asyncio
    async def test_separate_topics_isolated(self):
        b = MemoryBroker()
        await b.connect()
        await b.publish("topic-a", BrokerMessage(payload={"src": "a"}))
        await b.publish("topic-b", BrokerMessage(payload={"src": "b"}))

        got_a, got_b = [], []
        async def drain(topic, bucket):
            async for m in b.subscribe(topic):
                bucket.append(m)
                break

        await asyncio.gather(drain("topic-a", got_a), drain("topic-b", got_b))
        assert got_a[0].payload["src"] == "a"
        assert got_b[0].payload["src"] == "b"

    @pytest.mark.asyncio
    async def test_queue_full_drops_message(self):
        b = MemoryBroker(maxsize=2)
        await b.connect()
        for i in range(5):
            await b.publish("t", BrokerMessage(payload={"i": i}))
        # Should not raise, just drop silently


# ─────────────────────────────────────────────────────────────
# Broker factory
# ─────────────────────────────────────────────────────────────

class TestGetBroker:
    def setup_method(self):
        reset_broker()

    def teardown_method(self):
        reset_broker()

    def test_default_is_memory(self):
        b = get_broker()
        assert isinstance(b, MemoryBroker)

    def test_explicit_memory(self):
        b = get_broker("memory")
        assert isinstance(b, MemoryBroker)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown broker backend"):
            get_broker("nonexistent")

    def test_singleton_returned(self):
        b1 = get_broker()
        b2 = get_broker()
        assert b1 is b2

    def test_reset_clears_singleton(self):
        b1 = get_broker()
        reset_broker()
        b2 = get_broker()
        assert b1 is not b2


# ─────────────────────────────────────────────────────────────
# ChainProvider
# ─────────────────────────────────────────────────────────────

MOCK_BLOCK = {
    "number": "0x12D687",
    "hash":   "0xabc...",
    "transactions": [],
}

MOCK_TX = {
    "hash":        "0xdeadbeef",
    "from":        "0x" + "a" * 40,
    "to":          "0x" + "b" * 40,
    "value":       "0xDE0B6B3A7640000",  # 1 ETH
    "gasPrice":    "0x9502F900",
    "blockNumber": "0x12D687",
}


def make_mock_response(result):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": result}
    return resp


class TestChainProvider:
    @pytest.mark.asyncio
    async def test_get_latest_block_number(self):
        meta = CHAINS["ethereum"]
        provider = ChainProvider("ethereum", meta)

        with patch.object(provider, "_call", new_callable=AsyncMock, return_value="0x12D687"):
            block_num = await provider.get_latest_block_number()
        assert block_num == 0x12D687

    @pytest.mark.asyncio
    async def test_get_transaction(self):
        meta = CHAINS["ethereum"]
        provider = ChainProvider("ethereum", meta)

        with patch.object(provider, "_call", new_callable=AsyncMock, return_value=MOCK_TX):
            tx = await provider.get_transaction("0xdeadbeef")
        assert tx["hash"] == "0xdeadbeef"

    @pytest.mark.asyncio
    async def test_get_balance_returns_int(self):
        meta = CHAINS["ethereum"]
        provider = ChainProvider("ethereum", meta)

        with patch.object(provider, "_call", new_callable=AsyncMock, return_value="0xDE0B6B3A7640000"):
            bal = await provider.get_balance("0x" + "a" * 40)
        assert bal == 1_000_000_000_000_000_000  # 1 ETH in wei

    @pytest.mark.asyncio
    async def test_rpc_error_raises(self):
        meta = CHAINS["ethereum"]
        provider = ChainProvider("ethereum", meta)

        async def bad_call(*a, **kw):
            raise RuntimeError("RPC error")

        with patch.object(provider, "_call", side_effect=bad_call):
            with pytest.raises(RuntimeError):
                await provider.get_latest_block_number()

    def test_rpc_resolution_order_explicit(self, monkeypatch):
        monkeypatch.setenv("ETH_RPC_URL", "https://custom-rpc.example.com")
        meta = CHAINS["ethereum"]
        p = ChainProvider("ethereum", meta)
        assert p.rpc_url == "https://custom-rpc.example.com"
        monkeypatch.delenv("ETH_RPC_URL")

    def test_rpc_resolution_fallback(self, monkeypatch):
        monkeypatch.delenv("ETH_RPC_URL",      raising=False)
        monkeypatch.delenv("ETH_ALCHEMY_KEY",  raising=False)
        monkeypatch.delenv("ETH_INFURA_KEY",   raising=False)
        p = ChainProvider("ethereum", CHAINS["ethereum"])
        assert p.rpc_url == CHAINS["ethereum"].fallback_rpc


# ─────────────────────────────────────────────────────────────
# ChainRegistry
# ─────────────────────────────────────────────────────────────

class TestChainRegistry:
    def test_all_builtin_chains_load(self):
        registry = ChainRegistry()
        chains = registry.all_chains()
        assert "ethereum" in chains
        assert "polygon"  in chains
        assert "arbitrum" in chains

    def test_get_known_chain(self):
        registry = ChainRegistry()
        eth = registry.get("ethereum")
        assert isinstance(eth, ChainProvider)

    def test_get_unknown_raises(self):
        registry = ChainRegistry()
        with pytest.raises(KeyError):
            registry.get("not_a_chain")

    def test_restricted_init(self):
        registry = ChainRegistry(enabled_chains=["ethereum", "polygon"])
        assert "bsc" not in registry.all_chains()
        assert "ethereum" in registry.all_chains()

    @pytest.mark.asyncio
    async def test_health_check_structure(self):
        registry = ChainRegistry(enabled_chains=["ethereum"])
        eth = registry.get("ethereum")

        with patch.object(eth, "get_chain_id", new_callable=AsyncMock, return_value=1):
            with patch.object(eth, "get_latest_block_number", new_callable=AsyncMock, return_value=19_800_000):
                result = await registry.health_check()

        assert "ethereum" in result
        assert result["ethereum"]["status"] == "ok"
        assert result["ethereum"]["chain_id"] == 1

    @pytest.mark.asyncio
    async def test_health_check_error_captured(self):
        registry = ChainRegistry(enabled_chains=["ethereum"])
        eth = registry.get("ethereum")

        with patch.object(eth, "get_chain_id", side_effect=RuntimeError("timeout")):
            result = await registry.health_check()

        assert result["ethereum"]["status"] == "error"
        assert "timeout" in result["ethereum"]["error"]
