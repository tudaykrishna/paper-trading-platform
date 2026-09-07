"""Watchlist schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.instrument import InstrumentOut, QuoteOut


class WatchlistItemOut(BaseModel):
    id: int
    instrument_key: str
    position: int
    instrument: InstrumentOut | None = None
    quote: QuoteOut | None = None


class WatchlistOut(BaseModel):
    id: int
    name: str
    items: list[WatchlistItemOut]


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AddItemRequest(BaseModel):
    instrument_key: str = Field(min_length=3, max_length=64)


class ReorderRequest(BaseModel):
    instrument_keys: list[str]
