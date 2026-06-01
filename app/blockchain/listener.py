"""
app/blockchain/listener.py
Real-time Ethereum transaction listener using WebSocket (Alchemy / Infura).

Architecture:
  WebSocket → raw block → extract txs → ML scoring → Redis pub/sub → FastAPI WS

Falls back to HTTP polling when WebSocket URL is not configured.
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Dict, Any, List, Optional

from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
try:
    from web3.providers import WebSocketProvider as AsyncWebsocketProvider
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

from app.core.config import get_settings
from app.core.logger import get_logger

settings = get_settings()
logger = get_logger("blockshield.listener")

def _get_available_endpoints() -> List[Dict[str, Optional[str]]]:
    """Returns a list of prioritized endpoints, each containing a 'rpc' and optional 'ws' URL."""
    endpoints = []
    
    if getattr(settings, 'ETH_RPC_URL', None):
        is_ws = settings.ETH_RPC_URL.startswith("wss://")
        endpoints.append({
            "rpc": settings.ETH_RPC_URL if not is_ws else None,
            "ws": settings.ETH_RPC_URL if is_ws else None
        })
        
    if getattr(settings, 'ETH_ALCHEMY_KEY', None):
        endpoints.append({
            "rpc": f"https://eth-mainnet.g.alchemy.com/v2/{settings.ETH_ALCHEMY_KEY}",
            "ws": f"wss://eth-mainnet.g.alchemy.com/v2/{settings.ETH_ALCHEMY_KEY}"
        })
        
    if getattr(settings, 'ETH_INFURA_KEY', None):
        endpoints.append({
            "rpc": f"https://mainnet.infura.io/v3/{settings.ETH_INFURA_KEY}",
            "ws": f"wss://mainnet.infura.io/ws/v3/{settings.ETH_INFURA_KEY}"
        })
        
    endpoints.append({
        "rpc": "https://cloudflare-eth.com",
        "ws": None
    })
    
    return endpoints

# Type alias for transaction callback
TxCallback = Callable[[Dict[str, Any]], None]


def _wei_to_eth(wei: int) -> float:
    return wei / 1e18


def _wei_to_gwei(wei: int) -> float:
    return wei / 1e9


def _parse_tx(tx, block_number: int, block_timestamp: datetime) -> Dict[str, Any]:
    """Normalise a web3 transaction object into our internal dict format."""
    return {
        "hash": tx["hash"].hex() if hasattr(tx["hash"], "hex") else str(tx["hash"]),
        "block_number": block_number,
        "timestamp": block_timestamp,
        "from_address": tx.get("from", "").lower(),
        "to_address": (tx.get("to") or "").lower() or None,
        "value_eth": _wei_to_eth(tx.get("value", 0)),
        "gas": tx.get("gas", 21000),
        "gas_limit": tx.get("gas", 21000),
        "gas_price_gwei": _wei_to_gwei(tx.get("gasPrice", 0)),
        "input_data": tx.get("input", "0x") or "0x",
        "nonce": tx.get("nonce", 0),
    }


class BlockchainListener:
    """
    Subscribes to new Ethereum blocks and emits parsed transactions.

    Usage:
        listener = BlockchainListener()
        async for tx in listener.stream():
            print(tx)
    """

    def __init__(self):
        self._w3: Optional[AsyncWeb3] = None
        self._running = False
        self._callbacks: List[TxCallback] = []
        self._block_count = 0
        self._tx_count = 0
        self._endpoints = _get_available_endpoints()
        self._endpoint_index = 0
        self._current_is_ws = False

    def register_callback(self, fn: TxCallback) -> None:
        self._callbacks.append(fn)

    async def _get_web3(self) -> AsyncWeb3:
        if self._w3 is None:
            endpoint = self._endpoints[self._endpoint_index]
            ws_url = endpoint["ws"]
            rpc_url = endpoint["rpc"]
            
            if ws_url and WS_AVAILABLE:
                logger.info("Connecting via WebSocket", url=ws_url[:40] + "...")
                self._w3 = AsyncWeb3(AsyncWebsocketProvider(
                    ws_url,
                    websocket_kwargs={'ping_interval': 20, 'ping_timeout': 10}
                ))
                self._current_is_ws = True
            elif rpc_url:
                logger.info("Connecting via HTTP RPC", url=rpc_url[:40] + "...")
                self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
                self._current_is_ws = False
            else:
                raise ValueError("No valid RPC or WS URL found in current endpoint.")
        return self._w3

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Async generator — yields parsed transaction dicts as they arrive.
        Reconnects automatically on errors with exponential back-off and fails over to next RPC.
        """
        self._running = True
        backoff = 1.0

        while self._running:
            try:
                w3 = await self._get_web3()
                if not await w3.is_connected():
                    raise ConnectionError("Web3 not connected")

                logger.info("Blockchain listener connected")
                backoff = 1.0

                if self._current_is_ws:
                    async for tx in self._ws_stream(w3):
                        yield tx
                else:
                    async for tx in self._poll_stream(w3):
                        yield tx

            except Exception as exc:
                next_index = (self._endpoint_index + 1) % len(self._endpoints)
                logger.error("Listener error — reconnecting", error=str(exc), backoff=backoff, 
                             failover_to=f"Endpoint index {next_index}")
                self._w3 = None
                self._endpoint_index = next_index
                
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _ws_stream(self, w3: AsyncWeb3) -> AsyncIterator[Dict[str, Any]]:
        """Subscribe to newHeads via WebSocket."""
        subscription_id = await w3.eth.subscribe("newHeads")  # type: ignore[attr-defined]
        async for response in w3.socket.process_subscriptions():  # type: ignore[attr-defined]
            block_hash = response["result"]["hash"]
            block = await w3.eth.get_block(block_hash, full_transactions=True)
            ts = datetime.fromtimestamp(block["timestamp"], timezone.utc)
            self._block_count += 1

            for tx in block.get("transactions", []):
                parsed = _parse_tx(tx, block["number"], ts)
                self._tx_count += 1
                yield parsed

    async def _poll_stream(self, w3: AsyncWeb3, poll_interval: float = 12.0) -> AsyncIterator[Dict[str, Any]]:
        """HTTP polling fallback — fetches latest block every ~12 s."""
        last_block = await w3.eth.block_number

        while self._running:
            await asyncio.sleep(poll_interval)
            try:
                latest = await w3.eth.block_number
                for block_num in range(last_block + 1, latest + 1):
                    block = await w3.eth.get_block(block_num, full_transactions=True)
                    ts = datetime.fromtimestamp(block["timestamp"], timezone.utc)
                    self._block_count += 1

                    for tx in block.get("transactions", []):
                        parsed = _parse_tx(tx, block_num, ts)
                        self._tx_count += 1
                        yield parsed

                last_block = latest
            except Exception as exc:
                logger.warning("Poll error", error=str(exc))

    def stop(self):
        self._running = False

    @property
    def stats(self) -> Dict[str, int]:
        return {"blocks": self._block_count, "transactions": self._tx_count}


# ── Demo / simulation mode ────────────────────────────────────────────────────

class SimulatedListener:
    """
    Generates synthetic Ethereum transactions at configurable rate.
    Used when no API key is configured (demo mode).
    """

    def __init__(self, tx_per_second: float = 5.0):
        self.tx_per_second = tx_per_second
        self._tx_count = 0
        self._running = False

    async def stream(self) -> AsyncIterator[Dict[str, Any]]:
        import random
        self._running = True
        block_number = 19_000_000
        FLASH_LOAN_SIGS = ["0x5cffe9de", "0xab9c4b5d", "0xe0a4b5d3"]
        WALLETS = [f"0x{''.join([f'{random.randint(0,255):02x}' for _ in range(20)])}" for _ in range(50)]

        while self._running:
            await asyncio.sleep(1.0 / self.tx_per_second)
            # ~3 % chance of flash loan, ~5 % chance of high-value
            is_flash = random.random() < 0.03
            is_high_value = random.random() < 0.05

            self._tx_count += 1
            block_number += random.randint(0, 1)

            yield {
                "hash": f"0x{''.join([f'{random.randint(0,255):02x}' for _ in range(32)])}",
                "block_number": block_number,
                "timestamp": datetime.now(timezone.utc),
                "from_address": random.choice(WALLETS),
                "to_address": random.choice(WALLETS),
                "value_eth": random.uniform(100, 2000) if is_flash else
                             random.uniform(500, 5000) if is_high_value else
                             random.expovariate(1 / 0.5),
                "gas": random.randint(21000, 500000),
                "gas_limit": 500000,
                "gas_price_gwei": random.uniform(1, 300) if is_flash else random.uniform(10, 50),
                "input_data": random.choice(FLASH_LOAN_SIGS) + "00" * 32 if is_flash else "0x",
                "nonce": random.randint(0, 1000),
            }

    def stop(self):
        self._running = False

    @property
    def stats(self) -> Dict[str, int]:
        return {"blocks": 0, "transactions": self._tx_count}


def get_listener():
    """Return real listener if API key configured, else simulation."""
    if getattr(settings, 'ETH_ALCHEMY_KEY', None) or getattr(settings, 'ETH_INFURA_KEY', None) or getattr(settings, 'ETH_RPC_URL', None):
        return BlockchainListener()
    logger.warning("No API key configured — running in SIMULATION mode")
    return SimulatedListener(tx_per_second=8.0)
