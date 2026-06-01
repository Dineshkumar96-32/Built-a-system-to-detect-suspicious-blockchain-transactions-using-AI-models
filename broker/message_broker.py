import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

# pyrefly: ignore [missing-import]
import redis.asyncio as redis

logger = logging.getLogger(__name__)

@dataclass
class BrokerMessage:
    payload: Dict[str, Any]
    topic: str = "transactions"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps({
            "payload": self.payload,
            "topic": self.topic,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, data: str) -> "BrokerMessage":
        parsed = json.loads(data)
        return cls(
            payload=parsed["payload"],
            topic=parsed.get("topic", "transactions"),
            message_id=parsed["message_id"],
            timestamp=parsed["timestamp"],
        )

class BaseBroker(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def publish(self, topic: str, message: BrokerMessage) -> None:
        pass

    @abstractmethod
    async def subscribe(self, topic: str) -> AsyncGenerator[BrokerMessage, None]:
        pass

class MemoryBroker(BaseBroker):
    def __init__(self, maxsize: int = 0):
        # maxsize=0 means unlimited queue size for memory broker (prevents message loss)
        # Use large defaults for high-throughput topics
        self.maxsize = maxsize if maxsize > 0 else 10000  # Default to 10K capacity
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()
        self._drop_counts: Dict[str, int] = defaultdict(int)

    async def _get_queue(self, topic: str) -> asyncio.Queue:
        async with self._lock:
            if topic not in self._queues:
                # Larger queues for transactions, smaller for others
                topic_size = 50000 if topic == "transactions" else self.maxsize
                self._queues[topic] = asyncio.Queue(maxsize=topic_size)
            return self._queues[topic]

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def publish(self, topic: str, message: BrokerMessage) -> None:
        queue = await self._get_queue(topic)
        try:
            # Wait up to 1 second for queue space, then warn and drop
            await asyncio.wait_for(queue.put(message), timeout=1.0)
        except asyncio.TimeoutError:
            self._drop_counts[topic] += 1
            if self._drop_counts[topic] % 100 == 1:  # Log every 100th drop
                logger.warning(
                    "Message broker queue full: dropped %d messages on topic %s",
                    self._drop_counts[topic],
                    topic,
                )
        except asyncio.CancelledError:
            raise

    async def subscribe(self, topic: str) -> AsyncGenerator[BrokerMessage, None]:
        queue = await self._get_queue(topic)
        while True:
            msg = await queue.get()
            yield msg
            queue.task_done()

class RedisBroker(BaseBroker):
    def __init__(self, url: Optional[str] = None):
        from app.core.config import settings
        self.url = url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = redis.from_url(
                self.url, 
                decode_responses=True,
                health_check_interval=30
            )
            logger.info("Connected to Redis broker at %s", self.url)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            logger.info("Closed Redis broker connection")

    async def publish(self, topic: str, message: BrokerMessage) -> None:
        if self._redis is None:
            await self.connect()
        try:
            await self._redis.publish(topic, message.to_json())
        except Exception as e:
            logger.error("Failed to publish to redis: %s", str(e))

    async def subscribe(self, topic: str) -> AsyncGenerator[BrokerMessage, None]:
        if self._redis is None:
            await self.connect()
            
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(topic)
        logger.info("Subscribed to Redis topic: %s", topic)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = message["data"]
                        yield BrokerMessage.from_json(data)
                    except Exception as e:
                        logger.error("Failed to parse redis message: %s", str(e))
        finally:
            await pubsub.unsubscribe(topic)
            await pubsub.close()

_BROKER_INSTANCE: Optional[BaseBroker] = None

def get_broker(backend: str = "memory") -> BaseBroker:
    global _BROKER_INSTANCE
    if _BROKER_INSTANCE is not None:
        return _BROKER_INSTANCE

    if backend == "memory":
        _BROKER_INSTANCE = MemoryBroker()
        return _BROKER_INSTANCE
    elif backend == "redis":
        _BROKER_INSTANCE = RedisBroker()
        return _BROKER_INSTANCE
    else:
        raise ValueError(f"Unknown broker backend: {backend}")

def reset_broker() -> None:
    global _BROKER_INSTANCE
    _BROKER_INSTANCE = None
