"""Execution engine process: consume ticks from Redis, match resting orders."""
from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal

from app.db import SessionLocal
from app.redis_client import TICKS_CHANNEL, redis_client
from app.services.execution.engine import process_tick

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("engine")


async def run() -> None:
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(TICKS_CHANNEL)
    logger.info("engine: matching loop live on %s", TICKS_CHANNEL)

    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        try:
            tick = json.loads(message["data"])
        except (json.JSONDecodeError, TypeError):
            continue

        key = tick.get("instrument_key")
        ltp = tick.get("ltp")
        if not key or ltp is None:
            continue

        try:
            async with SessionLocal() as db:
                n = await process_tick(
                    db,
                    key,
                    Decimal(str(ltp)),
                    bid=Decimal(str(tick["bid"])) if tick.get("bid") else None,
                    ask=Decimal(str(tick["ask"])) if tick.get("ask") else None,
                )
                await db.commit()
                if n:
                    logger.info("filled %d order(s) on %s @ %s", n, key, ltp)
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            logger.exception("process_tick failed for %s: %s", key, exc)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
