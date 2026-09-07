"""Assemble QuoteOut objects from Redis tick cache with a provider fallback."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.schemas.instrument import QuoteOut
from app.services.instrument_service import cached_quote
from app.services.market_data.registry import get_provider

D = Decimal


def _pct(ltp: Decimal, prev: Decimal | None, opn: Decimal | None):
    """Day change vs previous close; falls back to today's open."""
    base = prev if (prev and prev > 0) else (opn if (opn and opn > 0) else None)
    if base is None:
        return None, None
    change = ltp - base
    return change, (change / base * 100).quantize(D("0.01"))


def _num(raw: dict, key: str) -> Decimal | None:
    v = raw.get(key)
    return D(str(v)) if v not in (None, "None", "") else None


def _q(raw: dict) -> QuoteOut:
    ltp = D(str(raw["ltp"])) if raw.get("ltp") is not None else D(0)
    prev = _num(raw, "prev_close")
    opn = _num(raw, "open")
    change, change_pct = _pct(ltp, prev, opn)
    ts = None
    if raw.get("ts"):
        try:
            ts = datetime.fromisoformat(raw["ts"])
        except ValueError:
            ts = None
    return QuoteOut(
        instrument_key=raw["instrument_key"],
        ltp=ltp,
        prev_close=prev,
        open=opn,
        high=_num(raw, "high"),
        low=_num(raw, "low"),
        change=change,
        change_pct=change_pct,
        volume=raw.get("volume"),
        oi=raw.get("oi"),
        ts=ts,
    )


async def quotes_for(instrument_keys: list[str]) -> dict[str, QuoteOut]:
    """Return a quote per key: Redis cache first, then a live provider fetch for misses."""
    out: dict[str, QuoteOut] = {}
    missing: list[str] = []
    for key in instrument_keys:
        raw = await cached_quote(key)
        if raw:
            out[key] = _q(raw)
        else:
            missing.append(key)

    if missing:
        try:
            provider = get_provider()
            fetched = await provider.get_quote(missing)
            for key, qd in fetched.items():
                change, change_pct = _pct(qd.ltp, qd.prev_close, qd.open)
                out[key] = QuoteOut(
                    instrument_key=key,
                    ltp=qd.ltp,
                    prev_close=qd.prev_close,
                    open=qd.open,
                    high=qd.high,
                    low=qd.low,
                    change=change,
                    change_pct=change_pct,
                    volume=qd.volume,
                    oi=qd.oi,
                    ts=qd.ts,
                )
        except Exception:  # noqa: BLE001 - quotes are best-effort
            pass
    return out
