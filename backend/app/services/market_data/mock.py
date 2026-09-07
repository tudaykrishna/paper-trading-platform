"""Deterministic mock provider.

Random-walk feed over a small equity set plus synthetic index F&O (NIFTY /
BANKNIFTY futures and an option chain), so every phase — including derivatives —
runs and tests without a broker account. Option premiums use a crude
intrinsic + decaying-time-value model; good enough for a paper simulator.
"""
from __future__ import annotations

import asyncio
import math
import random
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.enums import AssetCategory, Exchange, InstrumentType, Segment
from app.services.market_data.base import (
    Candle,
    InstrumentDTO,
    MarketDataProvider,
    OptionChainRow,
    QuoteDTO,
    TickDTO,
)

D = Decimal

_EQUITY: list[tuple[str, str, str, float]] = [
    ("NSE_EQ|INE002A01018", "RELIANCE", "Reliance Industries Ltd", 2900.0),
    ("NSE_EQ|INE467B01029", "TCS", "Tata Consultancy Services Ltd", 3850.0),
    ("NSE_EQ|INE040A01034", "HDFCBANK", "HDFC Bank Ltd", 1650.0),
    ("NSE_EQ|INE009A01021", "INFY", "Infosys Ltd", 1550.0),
    ("NSE_EQ|INE075A01022", "WIPRO", "Wipro Ltd", 470.0),
    ("NSE_EQ|INE154A01025", "ITC", "ITC Ltd", 450.0),
    ("NSE_EQ|INE030A01027", "HINDUNILVR", "Hindustan Unilever Ltd", 2400.0),
    ("NSE_EQ|INE238A01034", "AXISBANK", "Axis Bank Ltd", 1150.0),
]

# underlying_key, symbol, base level, lot size, strike step, # strikes each side
_INDICES: list[tuple[str, str, float, int, int, int]] = [
    ("NSE_INDEX|Nifty 50", "NIFTY", 24000.0, 50, 50, 6),
    ("NSE_INDEX|Nifty Bank", "BANKNIFTY", 51000.0, 15, 100, 6),
]

# key, symbol, name, exchange, segment, base price, lot size  (standalone futures)
_FUTURES: list[tuple[str, str, str, Exchange, Segment, float, int]] = [
    ("MCX_FO|GOLDM-FUT", "GOLDM", "Gold Mini Futures", Exchange.MCX, Segment.MCX, 7200.0, 100),
    ("MCX_FO|SILVERM-FUT", "SILVERM", "Silver Mini Futures", Exchange.MCX, Segment.MCX, 8900.0, 5),
    ("NCD_FO|USDINR-FUT", "USDINR", "USD/INR Futures", Exchange.CDS, Segment.CDS, 83.50, 1000),
]


def _last_thursday(d: date) -> date:
    """Monthly-expiry proxy: last Thursday of ``d``'s month, or next month if passed."""
    year, month = d.year, d.month
    last = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    while last.weekday() != 3:  # Thursday
        last -= timedelta(days=1)
    if last < d:
        return _last_thursday(date(year + (month == 12), (month % 12) + 1, 1))
    return last


def _round_strike(level: float, step: int) -> int:
    return int(round(level / step) * step)


class MockProvider(MarketDataProvider):
    name = "mock"

    def __init__(self, tick_interval: float = 1.0) -> None:
        self._tick_interval = tick_interval
        self._rng = random.Random(42)
        self._expiry = _last_thursday(datetime.now(timezone.utc).date())

        self._prices: dict[str, Decimal] = {}
        self._prev_close: dict[str, Decimal] = {}
        self._meta: dict[str, InstrumentDTO] = {}
        self._underlying_of: dict[str, tuple[str, int, str]] = {}  # opt key -> (underlying, strike, CE/PE)
        self._chain: dict[str, list[tuple[int, str, str]]] = {}    # underlying -> [(strike, ce_key, pe_key)]

        self._build_universe()
        self._subscribed: set[str] = set()

    # ---- construction ----------------------------------------------------

    def _add(self, dto: InstrumentDTO, price: float) -> None:
        self._meta[dto.instrument_key] = dto
        self._prices[dto.instrument_key] = D(str(round(price, 2)))
        self._prev_close[dto.instrument_key] = D(str(round(price, 2)))

    def _build_universe(self) -> None:
        for key, sym, name, px in _EQUITY:
            self._add(
                InstrumentDTO(key, Exchange.NSE, Segment.EQ, InstrumentType.EQUITY, sym, name,
                             category=AssetCategory.EQUITY, lot_size=1, tick_size=D("0.05")),
                px,
            )

        for key, sym, name, exch, seg, px, lot in _FUTURES:
            cat = AssetCategory.COMMODITY if seg == Segment.MCX else AssetCategory.CURRENCY
            self._add(
                InstrumentDTO(key, exch, seg, InstrumentType.FUT,
                              f"{sym}{self._expiry:%y%b}FUT".upper(), name,
                              category=cat, lot_size=lot, expiry=self._expiry),
                px,
            )

        for ukey, usym, level, lot, step, n in _INDICES:
            self._add(
                InstrumentDTO(ukey, Exchange.NSE, Segment.EQ, InstrumentType.INDEX, usym, usym,
                             category=AssetCategory.INDEX, lot_size=1),
                level,
            )
            fut_key = f"NSE_FO|{usym}-FUT-{self._expiry:%y%b}".upper()
            self._add(
                InstrumentDTO(fut_key, Exchange.NFO, Segment.FO, InstrumentType.FUT,
                              f"{usym}{self._expiry:%y%b}FUT".upper(), f"{usym} FUT",
                              category=AssetCategory.FUTURE,
                              lot_size=lot, expiry=self._expiry, underlying_key=ukey),
                level,
            )
            atm = _round_strike(level, step)
            chain: list[tuple[int, str, str]] = []
            for i in range(-n, n + 1):
                strike = atm + i * step
                ce_key = f"NSE_FO|{usym}{self._expiry:%y%b}{strike}CE".upper()
                pe_key = f"NSE_FO|{usym}{self._expiry:%y%b}{strike}PE".upper()
                for opt_key, opt_type in ((ce_key, "CE"), (pe_key, "PE")):
                    itype = InstrumentType.CE if opt_type == "CE" else InstrumentType.PE
                    self._add(
                        InstrumentDTO(
                            opt_key, Exchange.NFO, Segment.FO, itype,
                            f"{usym}{self._expiry:%y%b}{strike}{opt_type}".upper(),
                            f"{usym} {strike} {opt_type}",
                            category=AssetCategory.OPTION,
                            lot_size=lot, expiry=self._expiry,
                            strike=D(strike), underlying_key=ukey,
                        ),
                        self._option_price(level, strike, opt_type),
                    )
                    self._underlying_of[opt_key] = (ukey, strike, opt_type)
                chain.append((strike, ce_key, pe_key))
            self._chain[ukey] = chain

    def _dte(self) -> float:
        return max((self._expiry - datetime.now(timezone.utc).date()).days, 0)

    def _option_price(self, spot: float, strike: int, opt_type: str) -> float:
        intrinsic = max(0.0, spot - strike) if opt_type == "CE" else max(0.0, strike - spot)
        dist = abs(spot - strike)
        tv = 0.012 * spot * math.exp(-((dist / (0.04 * spot)) ** 2)) * (0.3 + self._dte() / 30)
        return max(0.05, round(intrinsic + tv, 2))

    def _reprice_derivatives(self) -> None:
        for ukey, _sym, _lvl, _lot, _step, _n in _INDICES:
            spot = float(self._prices[ukey])
            for k, meta in self._meta.items():
                if meta.underlying_key != ukey:
                    continue
                if meta.instrument_type == InstrumentType.FUT:
                    self._prices[k] = D(str(round(spot * 1.001, 2)))
                elif k in self._underlying_of:
                    _, strike, opt_type = self._underlying_of[k]
                    self._prices[k] = D(str(self._option_price(spot, strike, opt_type)))

    # ---- MarketDataProvider -------------------------------------------------

    async def authenticate(self) -> None:
        return None

    async def instrument_master(self) -> list[InstrumentDTO]:
        return list(self._meta.values())

    async def subscribe(self, instrument_keys: list[str]) -> None:
        self._subscribed.update(k for k in instrument_keys if k in self._prices)

    async def unsubscribe(self, instrument_keys: list[str]) -> None:
        self._subscribed.difference_update(instrument_keys)

    def _walk_underlyings(self) -> None:
        for key in list(self._prices):
            meta = self._meta.get(key)
            if meta and meta.underlying_key is not None:
                continue  # derivative — repriced from its underlying
            drift = D(str(self._rng.uniform(-0.0015, 0.0015)))
            px = (self._prices[key] * (D(1) + drift)).quantize(D("0.05"))
            self._prices[key] = max(px, D("1"))
        self._reprice_derivatives()

    async def stream(self) -> AsyncIterator[TickDTO]:
        while True:
            self._walk_underlyings()
            for key in list(self._subscribed) or list(self._prices):
                px = self._prices[key]
                yield TickDTO(
                    instrument_key=key,
                    ltp=px,
                    ts=datetime.now(timezone.utc),
                    bid=px - D("0.05"),
                    ask=px + D("0.05"),
                    prev_close=self._prev_close.get(key),
                )
            await asyncio.sleep(self._tick_interval)

    async def get_quote(self, instrument_keys: list[str]) -> dict[str, QuoteDTO]:
        out: dict[str, QuoteDTO] = {}
        for key in instrument_keys:
            if key not in self._prices:
                continue
            px = self._prices[key]
            pc = self._prev_close.get(key, px)
            out[key] = QuoteDTO(
                instrument_key=key, ltp=px, prev_close=pc,
                open=pc, high=max(px, pc), low=min(px, pc),
                ts=datetime.now(timezone.utc),
            )
        return out

    async def get_candles(
        self, instrument_key: str, interval: str, frm: datetime, to: datetime
    ) -> list[Candle]:
        base = self._prices.get(instrument_key, D("100"))
        step = timedelta(minutes=1 if interval in {"1minute", "1m"} else 1440)
        rng = random.Random(hash((instrument_key, frm.isoformat())) & 0xFFFF)
        candles: list[Candle] = []
        t = frm
        px = base
        while t < to:
            o = px
            c = (o * D(str(1 + rng.uniform(-0.01, 0.01)))).quantize(D("0.05"))
            hi = (max(o, c) * D("1.003")).quantize(D("0.05"))
            lo = (min(o, c) * D("0.997")).quantize(D("0.05"))
            candles.append(Candle(ts=t, open=o, high=hi, low=lo, close=c,
                                  volume=rng.randint(1_000, 50_000)))
            px = c
            t += step
        return candles

    async def get_option_chain(self, underlying_key: str, expiry: date) -> list[OptionChainRow]:
        chain = self._chain.get(underlying_key)
        if not chain:
            return []
        rows: list[OptionChainRow] = []
        for strike, ce_key, pe_key in chain:
            rows.append(
                OptionChainRow(
                    strike=D(strike),
                    expiry=self._expiry,
                    call=QuoteDTO(instrument_key=ce_key, ltp=self._prices[ce_key]),
                    put=QuoteDTO(instrument_key=pe_key, ltp=self._prices[pe_key]),
                    call_oi=1000 + strike % 7 * 137,
                    put_oi=1000 + strike % 5 * 149,
                )
            )
        return rows
