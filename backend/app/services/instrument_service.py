"""Instrument master sync + lookup + live-quote helpers."""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlalchemy import delete, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Instrument
from app.models.enums import CATEGORY_RANK, AssetCategory, Segment
from app.redis_client import quote_key, redis_client
from app.services.market_data.base import InstrumentDTO
from app.services.market_data.registry import get_provider

logger = logging.getLogger("instrument_service")


async def sync_instrument_master(db: AsyncSession, *, segments: set[Segment] | None = None) -> int:
    """Replace the ``instruments`` table with the provider's current universe.

    It's a full daily snapshot and nothing has a real FK to ``instruments``
    (orders/positions keep a plain ``instrument_key`` string), so a
    delete + bulk-insert is simplest and dialect-agnostic.
    """
    provider = get_provider()
    await provider.authenticate()
    dtos = await provider.instrument_master()
    if segments:
        dtos = [d for d in dtos if d.segment in segments]
    if not dtos:
        logger.warning("instrument master returned 0 rows — leaving table unchanged")
        return 0

    seen: set[str] = set()
    rows: list[dict] = []
    for d in dtos:
        if d.instrument_key in seen:
            continue
        seen.add(d.instrument_key)
        rows.append(
            {
                "instrument_key": d.instrument_key,
                "exchange": d.exchange,
                "segment": d.segment,
                "instrument_type": d.instrument_type,
                "category": d.category.value,
                "tradingsymbol": d.tradingsymbol,
                "name": d.name or d.tradingsymbol,
                "isin": d.isin,
                "lot_size": d.lot_size,
                "tick_size": d.tick_size,
                "freeze_qty": d.freeze_qty,
                "expiry": d.expiry,
                "strike": d.strike,
                "underlying_key": d.underlying_key,
            }
        )

    await db.execute(delete(Instrument))
    for i in range(0, len(rows), 5000):
        await db.execute(insert(Instrument), rows[i : i + 5000])
    await db.flush()
    logger.info("instrument master synced: %d rows", len(rows))
    return len(rows)


async def seed_from_dtos(db: AsyncSession, dtos: list[InstrumentDTO]) -> int:
    """Insert a specific list of instruments (used by the mock provider / tests)."""
    for d in dtos:
        exists = (
            await db.execute(
                select(Instrument.id).where(Instrument.instrument_key == d.instrument_key)
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(
            Instrument(
                instrument_key=d.instrument_key,
                exchange=d.exchange,
                segment=d.segment,
                instrument_type=d.instrument_type,
                category=d.category.value,
                tradingsymbol=d.tradingsymbol,
                name=d.name or d.tradingsymbol,
                isin=d.isin,
                lot_size=d.lot_size,
                tick_size=d.tick_size,
                expiry=d.expiry,
                strike=d.strike,
                underlying_key=d.underlying_key,
            )
        )
    await db.flush()
    return len(dtos)


_CAT_RANK = {c.value: r for c, r in CATEGORY_RANK.items()}


def _rank_key(inst: Instrument, qu: str) -> tuple:
    sym = (inst.tradingsymbol or "").upper()
    match_rank = 0 if sym == qu else (1 if sym.startswith(qu) else 2)
    cat_rank = _CAT_RANK.get(str(inst.category), 99)
    return (match_rank, cat_rank, len(sym), sym)


async def search(
    db: AsyncSession,
    q: str,
    *,
    segment: Segment | None = None,
    category: AssetCategory | None = None,
    limit: int = 20,
):
    """Search by symbol / name.

    Filtering is done in SQL; ranking (exact symbol → prefix → category priority
    → shortest symbol) is done in Python so it never depends on how the
    ``category`` column is typed in the database.
    """
    q = q.strip()
    stmt = select(Instrument)
    if q:
        qu = q.upper()
        stmt = stmt.where(
            or_(Instrument.tradingsymbol.ilike(f"{qu}%"), Instrument.name.ilike(f"%{qu}%"))
        )
    else:
        qu = ""
    if segment:
        stmt = stmt.where(Instrument.segment == segment)

    # over-fetch; category filter + ranking happen in Python so this query never
    # compares the `category` column (avoids enum/varchar type mismatches).
    rows = (await db.execute(stmt.limit(max(limit * 20, 500)))).scalars().all()
    if category:
        want = category.value
        rows = [r for r in rows if str(r.category) == want]
    rows.sort(key=lambda i: _rank_key(i, qu))
    return rows[:limit]


async def get_by_key(db: AsyncSession, instrument_key: str) -> Instrument:
    inst = (
        await db.execute(select(Instrument).where(Instrument.instrument_key == instrument_key))
    ).scalar_one_or_none()
    if inst is None:
        raise NotFoundError(f"unknown instrument {instrument_key}")
    return inst


async def cached_quote(instrument_key: str) -> dict | None:
    """Latest tick JSON the ``marketdata`` worker wrote to Redis, if any.

    Returns ``None`` (not an error) when Redis is unreachable — callers fall back
    to a live provider fetch.
    """
    try:
        raw = await redis_client.get(quote_key(instrument_key))
    except Exception:  # noqa: BLE001 - Redis optional for read paths
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def last_price(instrument_key: str) -> Decimal | None:
    q = await cached_quote(instrument_key)
    if q and q.get("ltp") is not None:
        return Decimal(str(q["ltp"]))
    return None
