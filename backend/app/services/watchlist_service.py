"""Watchlist CRUD used by the API and by user bootstrap."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models import Instrument, Watchlist, WatchlistItem
from app.models.enums import AssetCategory, Exchange

# Popular NSE/BSE names every user's default list starts with. Resolved to real
# instrument_keys from the synced instrument table at seed time; any not found
# (instruments not synced yet, or a symbol the provider spells differently) are
# skipped. Index aliases cover the Upstox ("Nifty 50") vs mock ("NIFTY") spellings.
DEFAULT_SYMBOLS: list[str] = [
    "NIFTY 50", "NIFTY", "NIFTY BANK", "BANKNIFTY", "SENSEX", "NIFTY IT",
    "RELIANCE", "HDFCBANK", "TCS", "INFY", "ICICIBANK", "BHARTIARTL",
    "SBIN", "ITC", "LT", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
    "HINDUNILVR", "MARUTI", "SUNPHARMA", "TATAMOTORS", "WIPRO",
]
DEFAULT_LIMIT = 22


async def _resolve_default_instruments(db: AsyncSession) -> list[Instrument]:
    upper = [s.upper() for s in DEFAULT_SYMBOLS]
    rows = (
        await db.execute(
            select(Instrument).where(
                func.upper(Instrument.tradingsymbol).in_(upper),
                Instrument.category.in_(
                    [AssetCategory.EQUITY.value, AssetCategory.INDEX.value]
                ),
            )
        )
    ).scalars().all()

    # one per symbol, preferring NSE over BSE
    picked: dict[str, Instrument] = {}
    for r in rows:
        k = r.tradingsymbol.upper()
        if k not in picked or r.exchange == Exchange.NSE:
            picked[k] = r

    order = {s.upper(): i for i, s in enumerate(DEFAULT_SYMBOLS)}
    return sorted(picked.values(), key=lambda r: order.get(r.tradingsymbol.upper(), 99))[:DEFAULT_LIMIT]


async def seed_popular(db: AsyncSession, watchlist_id: int) -> int:
    """Fill a watchlist with the default popular instruments (skips any already present)."""
    existing = set(
        (
            await db.execute(
                select(WatchlistItem.instrument_key).where(
                    WatchlistItem.watchlist_id == watchlist_id
                )
            )
        ).scalars().all()
    )
    start = len(existing)
    added = 0
    for inst in await _resolve_default_instruments(db):
        if inst.instrument_key in existing:
            continue
        db.add(
            WatchlistItem(
                watchlist_id=watchlist_id,
                instrument_key=inst.instrument_key,
                position=start + added,
            )
        )
        added += 1
    await db.flush()
    return added


async def create_default(db: AsyncSession, user_id: int) -> Watchlist:
    wl = Watchlist(user_id=user_id, name="Popular")
    db.add(wl)
    await db.flush()
    await seed_popular(db, wl.id)
    return wl


async def list_for_user(db: AsyncSession, user_id: int) -> list[Watchlist]:
    rows = (
        await db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .options(selectinload(Watchlist.items))
            .order_by(Watchlist.id)
        )
    ).scalars().all()
    if not rows:
        rows = [await create_default(db, user_id)]
    return list(rows)


async def _owned(db: AsyncSession, user_id: int, watchlist_id: int) -> Watchlist:
    wl = (
        await db.execute(
            select(Watchlist)
            .where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
            .options(selectinload(Watchlist.items))
        )
    ).scalar_one_or_none()
    if wl is None:
        raise NotFoundError("watchlist not found")
    return wl


async def add_item(db: AsyncSession, user_id: int, watchlist_id: int, instrument_key: str) -> Watchlist:
    wl = await _owned(db, user_id, watchlist_id)
    if any(it.instrument_key == instrument_key for it in wl.items):
        return wl
    if len(wl.items) >= 50:
        raise ValidationError("watchlist is full (50 max)")
    next_pos = max((it.position for it in wl.items), default=-1) + 1
    db.add(WatchlistItem(watchlist_id=wl.id, instrument_key=instrument_key, position=next_pos))
    await db.flush()
    await db.refresh(wl, ["items"])
    return wl


async def remove_item(db: AsyncSession, user_id: int, watchlist_id: int, instrument_key: str) -> Watchlist:
    wl = await _owned(db, user_id, watchlist_id)
    for it in list(wl.items):
        if it.instrument_key == instrument_key:
            await db.delete(it)
    await db.flush()
    await db.refresh(wl, ["items"])
    return wl


async def reorder(db: AsyncSession, user_id: int, watchlist_id: int, keys: list[str]) -> Watchlist:
    wl = await _owned(db, user_id, watchlist_id)
    order = {k: i for i, k in enumerate(keys)}
    for it in wl.items:
        if it.instrument_key in order:
            it.position = order[it.instrument_key]
    await db.flush()
    await db.refresh(wl, ["items"])
    return wl


async def all_watched_keys(db: AsyncSession) -> set[str]:
    """Every instrument on any user's watchlist (for the marketdata subscription set)."""
    rows = (await db.execute(select(WatchlistItem.instrument_key).distinct())).scalars().all()
    return set(rows)
