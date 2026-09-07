"""Watchlist endpoints, with live quotes + instrument metadata attached."""
from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models import Instrument, Watchlist
from app.schemas.instrument import InstrumentOut
from app.schemas.watchlist import (
    AddItemRequest,
    ReorderRequest,
    WatchlistCreate,
    WatchlistItemOut,
    WatchlistOut,
)
from app.services import market_service, watchlist_service

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


async def _serialize(db, watchlists: list[Watchlist]) -> list[WatchlistOut]:
    keys = {it.instrument_key for wl in watchlists for it in wl.items}
    instruments: dict[str, Instrument] = {}
    if keys:
        rows = (
            await db.execute(select(Instrument).where(Instrument.instrument_key.in_(keys)))
        ).scalars().all()
        instruments = {r.instrument_key: r for r in rows}
    quotes = await market_service.quotes_for(list(keys)) if keys else {}

    out: list[WatchlistOut] = []
    for wl in watchlists:
        items = sorted(wl.items, key=lambda it: it.position)
        out.append(
            WatchlistOut(
                id=wl.id,
                name=wl.name,
                items=[
                    WatchlistItemOut(
                        id=it.id,
                        instrument_key=it.instrument_key,
                        position=it.position,
                        instrument=(
                            InstrumentOut.model_validate(instruments[it.instrument_key])
                            if it.instrument_key in instruments
                            else None
                        ),
                        quote=quotes.get(it.instrument_key),
                    )
                    for it in items
                ],
            )
        )
    return out


@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(user: CurrentUser, db: DbSession):
    return await _serialize(db, await watchlist_service.list_for_user(db, user.id))


@router.post("/seed-popular", response_model=list[WatchlistOut])
async def seed_popular(user: CurrentUser, db: DbSession):
    """Add the default popular instruments to the user's first watchlist.

    Useful for accounts created before the default list was seeded, or after an
    instrument sync makes more of the popular names resolvable.
    """
    lists = await watchlist_service.list_for_user(db, user.id)
    await watchlist_service.seed_popular(db, lists[0].id)
    db.expunge_all()  # drop the cached (pre-seed) Watchlist so the re-read is fresh
    return await _serialize(db, await watchlist_service.list_for_user(db, user.id))


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist(payload: WatchlistCreate, user: CurrentUser, db: DbSession):
    wl = Watchlist(user_id=user.id, name=payload.name)
    db.add(wl)
    await db.flush()
    await db.refresh(wl, ["items"])
    return (await _serialize(db, [wl]))[0]


@router.post("/{watchlist_id}/items", response_model=WatchlistOut)
async def add_item(watchlist_id: int, payload: AddItemRequest, user: CurrentUser, db: DbSession):
    wl = await watchlist_service.add_item(db, user.id, watchlist_id, payload.instrument_key)
    return (await _serialize(db, [wl]))[0]


@router.delete("/{watchlist_id}/items/{instrument_key:path}", response_model=WatchlistOut)
async def remove_item(watchlist_id: int, instrument_key: str, user: CurrentUser, db: DbSession):
    wl = await watchlist_service.remove_item(db, user.id, watchlist_id, instrument_key)
    return (await _serialize(db, [wl]))[0]


@router.put("/{watchlist_id}/order", response_model=WatchlistOut)
async def reorder_items(
    watchlist_id: int, payload: ReorderRequest, user: CurrentUser, db: DbSession
):
    wl = await watchlist_service.reorder(db, user.id, watchlist_id, payload.instrument_keys)
    return (await _serialize(db, [wl]))[0]
