"""Market data service.

Drives the provider subscription set from every user's watchlist plus all open
positions/holdings, publishes normalized ticks to Redis, and refreshes the
subscription set periodically.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Holding, Position, WatchlistItem
from app.redis_client import TICKS_CHANNEL, quote_key, redis_client
from app.services.market_data.registry import get_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marketdata")

RESUBSCRIBE_EVERY = 10   # seconds — how fast a newly-watchlisted symbol goes live
QUOTE_TTL = 180          # seconds — stale quotes expire so the UI never shows ancient prices
HEARTBEAT_EVERY = 30     # seconds — log throughput so it's obvious whether ticks flow


def _tick_payload(tick) -> str:
    return json.dumps(
        {
            "instrument_key": tick.instrument_key,
            "ltp": str(tick.ltp),
            "ts": tick.ts.isoformat(),
            "bid": str(tick.bid) if tick.bid is not None else None,
            "ask": str(tick.ask) if tick.ask is not None else None,
            "prev_close": str(tick.prev_close) if tick.prev_close is not None else None,
            "open": str(tick.open) if tick.open is not None else None,
            "volume": tick.volume,
            "oi": tick.oi,
        }
    )


async def _desired_keys() -> set[str]:
    async with SessionLocal() as db:
        watched = set(
            (await db.execute(select(WatchlistItem.instrument_key).distinct())).scalars().all()
        )
        pos = set(
            (
                await db.execute(
                    select(Position.instrument_key).where(Position.net_qty != 0).distinct()
                )
            ).scalars().all()
        )
        hold = set(
            (
                await db.execute(
                    select(Holding.instrument_key).where(Holding.qty != 0).distinct()
                )
            ).scalars().all()
        )
    return watched | pos | hold


async def _resubscriber(provider) -> None:
    current: set[str] = set()
    while True:
        try:
            desired = await _desired_keys()
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not read desired keys: %s", exc)
            desired = current
        add = desired - current
        drop = current - desired
        if add:
            await provider.subscribe(list(add))
        if drop:
            await provider.unsubscribe(list(drop))
        if add or drop:
            logger.info(
                "subscription set: %d instruments (+%d -%d) %s",
                len(desired), len(add), len(drop), sorted(desired)[:12],
            )
        current = desired
        await asyncio.sleep(RESUBSCRIBE_EVERY)


async def run() -> None:
    provider = get_provider()
    try:
        await provider.authenticate()
    except Exception as exc:  # noqa: BLE001
        logger.error("market data provider auth failed: %s", exc)
        sys.exit(1)

    # For the mock provider, make sure something streams even before any watchlist exists.
    if provider.name == "mock":
        await provider.subscribe([i.instrument_key for i in await provider.instrument_master()])

    resub = asyncio.create_task(_resubscriber(provider))
    logger.info("marketdata: provider=%s (resubscribe every %ds)", provider.name, RESUBSCRIBE_EVERY)

    ticks = 0
    last_hb = time.monotonic()
    seen: set[str] = set()

    try:
        async for tick in provider.stream():
            payload = _tick_payload(tick)
            await redis_client.set(quote_key(tick.instrument_key), payload, ex=QUOTE_TTL)
            await redis_client.publish(TICKS_CHANNEL, payload)
            ticks += 1
            if tick.instrument_key not in seen:
                seen.add(tick.instrument_key)
                logger.info("first tick %s @ %s", tick.instrument_key, tick.ltp)

            now = time.monotonic()
            if now - last_hb >= HEARTBEAT_EVERY:
                logger.info("published %d ticks / %ds (%d instruments live)",
                            ticks, HEARTBEAT_EVERY, len(seen))
                ticks = 0
                last_hb = now
    except Exception as exc:  # noqa: BLE001
        logger.error("market data stream stopped: %s", exc)
        resub.cancel()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
