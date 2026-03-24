import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)


class EventBus:
    """Redis Pub/Sub Event Bus for inter-service communication."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        settings = get_settings()
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("EventBus connected to Redis")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("EventBus disconnected from Redis")

    async def publish(self, channel: str, event: dict) -> None:
        """Publish an event to a Redis channel."""
        if not self._redis:
            await self.connect()
        try:
            message = json.dumps(event)
            await self._redis.publish(channel, message)
            logger.debug(f"Published event to channel '{channel}': {event}")
        except Exception as e:
            logger.error(f"Failed to publish event to channel '{channel}': {e}")
            raise

    async def subscribe(self, channel: str) -> aioredis.client.PubSub:
        """Subscribe to a Redis channel. Returns a PubSub object."""
        if not self._redis:
            await self.connect()
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        logger.debug(f"Subscribed to channel '{channel}'")
        return pubsub

    async def unsubscribe(self, pubsub: aioredis.client.PubSub, channel: str) -> None:
        """Unsubscribe from a Redis channel."""
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


event_bus = EventBus()
