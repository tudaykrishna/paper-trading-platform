"""One-call health check for the live-data pipeline — no auth, open it in a browser.

    http://localhost:8000/api/debug/feed

  provider           : configured market-data provider
  redis_ok           : API can reach Redis
  quote_keys         : how many quote:* keys are cached
  samples            : a few cached quotes with their age in seconds
  channel_ticks_500ms: ticks seen on the `ticks` channel in a 0.5s window
                       (> 0  => marketdata IS publishing right now)
  candles            : newest daily-candle timestamp for RELIANCE + count
                       (tells you if chart data is fresh or lagging)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.config import settings
from app.redis_client import TICKS_CHANNEL, redis_client
from app.services.market_data.registry import get_provider

router = APIRouter(prefix="/api/debug", tags=["debug"])

_PROBE_KEY = "NSE_EQ|INE002A01018"  # RELIANCE


@router.get("/feed")
async def feed_health() -> dict:
    out: dict = {"provider": settings.market_data_provider, "now_utc": datetime.now(timezone.utc).isoformat()}

    try:
        await redis_client.ping()
        out["redis_ok"] = True
    except Exception as exc:  # noqa: BLE001
        return {**out, "redis_ok": False, "error": str(exc)}

    # cached quotes + freshness
    keys: list[str] = []
    try:
        async for k in redis_client.scan_iter(match="quote:*", count=200):
            keys.append(k)
    except Exception as exc:  # noqa: BLE001
        out["scan_error"] = str(exc)
    out["quote_keys"] = len(keys)

    samples = []
    now = datetime.now(timezone.utc)
    for k in keys[:6]:
        raw = await redis_client.get(k)
        if not raw:
            continue
        try:
            q = json.loads(raw)
            ts = datetime.fromisoformat(q["ts"])
            samples.append(
                {"key": k.split(":", 1)[-1], "ltp": q.get("ltp"),
                 "age_seconds": round((now - ts).total_seconds(), 1)}
            )
        except Exception:  # noqa: BLE001
            samples.append({"key": k, "raw": raw[:120]})
    out["samples"] = samples

    # is marketdata publishing right now?
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(TICKS_CHANNEL)
    seen = 0
    deadline = time.monotonic() + 0.5
    try:
        while time.monotonic() < deadline:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if msg and msg.get("type") == "message":
                seen += 1
    finally:
        await pubsub.close()
    out["channel_ticks_500ms"] = seen

    # chart data freshness
    try:
        provider = get_provider()
        await provider.authenticate()
        to = datetime.now(timezone.utc)
        candles = await provider.get_candles(_PROBE_KEY, "day", to - timedelta(days=12), to)
        out["candles"] = {
            "count": len(candles),
            "newest_ts": candles[-1].ts.isoformat() if candles else None,
            "oldest_ts": candles[0].ts.isoformat() if candles else None,
        }
    except Exception as exc:  # noqa: BLE001
        out["candles"] = {"error": str(exc)}

    if seen > 0:
        out["verdict"] = "feed live — ticks flowing"
    elif out["quote_keys"] == 0:
        out["verdict"] = "marketdata NOT publishing — check `docker compose logs marketdata`"
    else:
        oldest_age = max((s.get("age_seconds", 0) for s in samples), default=0)
        out["verdict"] = (
            f"quotes cached but no new ticks (oldest {oldest_age}s old) — "
            "marketdata stopped, or the Upstox token expired, or market closed"
        )
    return out
