"""Instrument + market-data response schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import AssetCategory, Exchange, InstrumentType, Segment


class InstrumentOut(BaseModel):
    instrument_key: str
    exchange: Exchange
    segment: Segment
    instrument_type: InstrumentType
    category: AssetCategory
    tradingsymbol: str
    name: str
    lot_size: int
    tick_size: Decimal
    expiry: date | None = None
    strike: Decimal | None = None
    underlying_key: str | None = None

    model_config = {"from_attributes": True}


class QuoteOut(BaseModel):
    instrument_key: str
    ltp: Decimal
    prev_close: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None
    oi: int | None = None
    ts: datetime | None = None


class CandleOut(BaseModel):
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OptionChainRowOut(BaseModel):
    strike: Decimal
    expiry: date
    call_key: str | None = None
    put_key: str | None = None
    call_ltp: Decimal | None = None
    put_ltp: Decimal | None = None
    call_oi: int = 0
    put_oi: int = 0
