"""Shared async Redis client and key helpers."""
from __future__ import annotations

import redis.asyncio as redis

from app.config import settings

# Fail fast when Redis is down rather than hanging request paths.
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=3,
    retry_on_timeout=False,
)

# Channels
TICKS_CHANNEL = "ticks"
ORDER_UPDATES_CHANNEL = "order_updates"
POSITION_UPDATES_CHANNEL = "position_updates"


def quote_key(instrument_key: str) -> str:
    return f"quote:{instrument_key}"


def open_orders_key(instrument_key: str) -> str:
    """Redis set of open order ids resting on an instrument."""
    return f"open_orders:{instrument_key}"


def user_channel(user_id: int) -> str:
    """Per-user fan-out channel the API relays to the browser WebSocket."""
    return f"user:{user_id}"
