"""Instrument search, quotes, historical candles, option chain."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError, ValidationError
from app.models import Instrument
from app.models.enums import AssetCategory, InstrumentType, Segment
from app.schemas.instrument import (
    CandleOut,
    InstrumentOut,
    OptionChainRowOut,
    QuoteOut,
)
from app.services import instrument_service, market_service
from app.services.market_data.registry import get_provider

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.post("/sync")
async def sync_instruments(db: DbSession, _: CurrentUser) -> dict:
    """Pull the provider's instrument master into the DB (also runs on scheduler boot)."""
    n = await instrument_service.sync_instrument_master(db)
    return {"synced": n}


@router.get("/categories", response_model=list[str])
async def list_categories(_: CurrentUser) -> list[str]:
    return [c.value for c in AssetCategory]


@router.get("/search", response_model=list[InstrumentOut])
async def search_instruments(
    db: DbSession,
    _: CurrentUser,
    q: str = Query("", min_length=0, max_length=40),
    segment: Segment | None = None,
    category: AssetCategory | None = None,
    limit: int = Query(20, le=50),
):
    return await instrument_service.search(
        db, q, segment=segment, category=category, limit=limit
    )


@router.get("/by-key", response_model=list[InstrumentOut])
async def get_by_keys(
    db: DbSession,
    _: CurrentUser,
    keys: str = Query(..., description="comma-separated instrument keys"),
):
    key_list = [k for k in keys.split(",") if k]
    if not key_list:
        return []
    rows = (
        await db.execute(select(Instrument).where(Instrument.instrument_key.in_(key_list)))
    ).scalars().all()
    return list(rows)


@router.get("/quote", response_model=dict[str, QuoteOut])
async def get_quotes(
    _: CurrentUser,
    keys: str = Query(..., description="comma-separated instrument keys"),
):
    key_list = [k for k in keys.split(",") if k]
    if not key_list:
        raise ValidationError("no instrument keys given")
    return await market_service.quotes_for(key_list)


@router.get("/expiries", response_model=list[date])
async def list_expiries(db: DbSession, _: CurrentUser, underlying_key: str = Query(...)):
    rows = (
        await db.execute(
            select(Instrument.expiry)
            .where(Instrument.underlying_key == underlying_key, Instrument.expiry.is_not(None))
            .distinct()
            .order_by(Instrument.expiry)
        )
    ).scalars().all()
    return [r for r in rows if r]


@router.get("/underlyings", response_model=list[InstrumentOut])
async def list_underlyings(db: DbSession, _: CurrentUser):
    """Indices / instruments that have F&O contracts."""
    keys = (
        await db.execute(
            select(Instrument.underlying_key)
            .where(Instrument.underlying_key.is_not(None))
            .distinct()
        )
    ).scalars().all()
    if not keys:
        return []
    return list(
        (
            await db.execute(select(Instrument).where(Instrument.instrument_key.in_(keys)))
        ).scalars().all()
    )


@router.get("/option-chain", response_model=list[OptionChainRowOut])
async def option_chain(
    db: DbSession,
    _: CurrentUser,
    underlying_key: str = Query(...),
    expiry: date | None = Query(None),
):
    if expiry is None:
        expiry = (
            await db.execute(
                select(Instrument.expiry)
                .where(Instrument.underlying_key == underlying_key, Instrument.expiry.is_not(None))
                .order_by(Instrument.expiry)
                .limit(1)
            )
        ).scalar_one_or_none()
        if expiry is None:
            raise NotFoundError("no expiries for this underlying")
    provider = get_provider()
    try:
        rows = await provider.get_option_chain(underlying_key, expiry)
    except NotImplementedError as exc:
        raise NotFoundError("option chain not available for this provider") from exc
    return [
        OptionChainRowOut(
            strike=r.strike,
            expiry=r.expiry,
            call_key=r.call.instrument_key if r.call else None,
            put_key=r.put.instrument_key if r.put else None,
            call_ltp=r.call.ltp if r.call else None,
            put_ltp=r.put.ltp if r.put else None,
            call_oi=r.call_oi,
            put_oi=r.put_oi,
        )
        for r in rows
    ]


@router.get("/{instrument_key:path}/candles", response_model=list[CandleOut])
async def get_candles(
    _: CurrentUser,
    instrument_key: str,
    interval: str = Query("day", pattern="^(1minute|30minute|day|week|month)$"),
    days: int = Query(120, ge=1, le=2000),
):
    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=days)
    provider = get_provider()
    candles = await provider.get_candles(instrument_key, interval, frm, to)
    return [
        CandleOut(ts=c.ts, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume)
        for c in candles
    ]
