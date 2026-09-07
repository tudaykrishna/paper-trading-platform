"""Provider-agnostic market data interface.

Concrete adapters (Upstox, mock, later Kite/Dhan) implement this so the rest of
the system never depends on a specific broker.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import AssetCategory, Exchange, InstrumentType, Segment


@dataclass(slots=True)
class InstrumentDTO:
    instrument_key: str
    exchange: Exchange
    segment: Segment
    instrument_type: InstrumentType
    tradingsymbol: str
    name: str = ""
    category: AssetCategory = AssetCategory.OTHER
    isin: str | None = None
    lot_size: int = 1
    tick_size: Decimal = Decimal("0.05")
    freeze_qty: int | None = None
    expiry: date | None = None
    strike: Decimal | None = None
    underlying_key: str | None = None


@dataclass(slots=True)
class TickDTO:
    instrument_key: str
    ltp: Decimal
    ts: datetime
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: int | None = None
    oi: int | None = None
    prev_close: Decimal | None = None
    open: Decimal | None = None


@dataclass(slots=True)
class QuoteDTO:
    instrument_key: str
    ltp: Decimal
    prev_close: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None
    oi: int | None = None
    ts: datetime | None = None


@dataclass(slots=True)
class Candle:
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    oi: int = 0


@dataclass(slots=True)
class OptionChainRow:
    strike: Decimal
    expiry: date
    call: QuoteDTO | None = None
    put: QuoteDTO | None = None
    call_oi: int = 0
    put_oi: int = 0


class MarketDataProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def authenticate(self) -> None:
        """Acquire / refresh whatever credentials the feed needs."""

    @abstractmethod
    async def instrument_master(self) -> list[InstrumentDTO]:
        """Full tradable universe for the day."""

    @abstractmethod
    async def subscribe(self, instrument_keys: list[str]) -> None:
        """Add instruments to the live stream."""

    @abstractmethod
    async def unsubscribe(self, instrument_keys: list[str]) -> None:
        ...

    @abstractmethod
    def stream(self) -> AsyncIterator[TickDTO]:
        """Yield normalized ticks until cancelled."""

    @abstractmethod
    async def get_quote(self, instrument_keys: list[str]) -> dict[str, QuoteDTO]:
        ...

    @abstractmethod
    async def get_candles(
        self, instrument_key: str, interval: str, frm: datetime, to: datetime
    ) -> list[Candle]:
        ...

    async def get_option_chain(
        self, underlying_key: str, expiry: date
    ) -> list[OptionChainRow]:
        raise NotImplementedError
