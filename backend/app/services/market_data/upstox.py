"""Upstox API v2 market-data adapter.

Design notes:
- The access token is supplied manually via ``UPSTOX_ACCESS_TOKEN`` (see README
  Step 3). There is **no auto-refresh** — when the token is rejected this adapter
  raises ``UpstoxAuthError`` and the caller (the ``marketdata`` worker) logs a
  clear message and exits.
- ``stream()`` is implemented by **polling** ``/v2/market-quote/quotes`` on a
  short interval rather than the protobuf WebSocket feed. It needs no extra
  dependencies, works outside market hours (returns last traded price), and is
  more than fast enough for a paper-trading simulator. Swapping in the WebSocket
  later only touches this file.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.config import settings
from app.models.enums import Exchange, InstrumentType, Segment
from app.services.market_data.base import (
    Candle,
    InstrumentDTO,
    MarketDataProvider,
    OptionChainRow,
    QuoteDTO,
    TickDTO,
)
from app.services.market_data.classify import classify_upstox

logger = logging.getLogger("marketdata.upstox")

BASE = "https://api.upstox.com/v2"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

# Upstox "segment" strings -> our Segment enum.
_SEGMENT_MAP = {
    "NSE_EQ": Segment.EQ,
    "BSE_EQ": Segment.EQ,
    "NSE_INDEX": Segment.EQ,
    "BSE_INDEX": Segment.EQ,
    "NSE_FO": Segment.FO,
    "BSE_FO": Segment.FO,
    "NCD_FO": Segment.CDS,
    "BCD_FO": Segment.CDS,
    "MCX_FO": Segment.MCX,
}
_EXCHANGE_MAP = {
    "NSE": Exchange.NSE,
    "BSE": Exchange.BSE,
    "NFO": Exchange.NFO,
    "BFO": Exchange.BFO,
    "CDS": Exchange.CDS,
    "BCD": Exchange.CDS,
    "MCX": Exchange.MCX,
}


class UpstoxAuthError(RuntimeError):
    """Raised when the Upstox access token is missing, expired, or rejected."""


def _to_instrument_type(raw: str, segment: Segment) -> InstrumentType:
    raw = (raw or "").upper()
    if raw in {"CE", "PE", "FUT"}:
        return InstrumentType(raw)
    if raw == "INDEX":
        return InstrumentType.INDEX
    return InstrumentType.EQUITY


class UpstoxProvider(MarketDataProvider):
    name = "upstox"

    def __init__(self, poll_interval: float = 1.0) -> None:
        self._token = settings.upstox_access_token.strip()
        self._poll_interval = poll_interval
        self._subscribed: set[str] = set()
        self._client = httpx.AsyncClient(timeout=15.0)

    # ---- helpers -------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise UpstoxAuthError(
                "UPSTOX_ACCESS_TOKEN is empty — generate one (README Step 3) and set it in .env"
            )
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        resp = await self._client.get(f"{BASE}{path}", headers=self._headers(), params=params)
        if resp.status_code in (401, 403):
            raise UpstoxAuthError(
                f"Upstox rejected the access token ({resp.status_code}). "
                "It has likely expired — regenerate it (README Step 3) and restart."
            )
        resp.raise_for_status()
        return resp.json()

    # ---- MarketDataProvider ------------------------------------------------

    async def authenticate(self) -> None:
        data = await self._get("/user/profile")
        who = data.get("data", {}).get("user_name", "?")
        logger.info("Upstox token OK (user=%s)", who)

    async def instrument_master(self) -> list[InstrumentDTO]:
        resp = await self._client.get(INSTRUMENTS_URL)
        resp.raise_for_status()
        raw = json.loads(gzip.decompress(resp.content))
        out: list[InstrumentDTO] = []
        for row in raw:
            seg_raw = row.get("segment", "")
            segment = _SEGMENT_MAP.get(seg_raw)
            if segment is None:
                continue
            exch = _EXCHANGE_MAP.get(row.get("exchange", ""), Exchange.NSE)
            itype = _to_instrument_type(row.get("instrument_type", ""), segment)
            expiry = None
            if row.get("expiry"):
                try:
                    expiry = datetime.fromtimestamp(int(row["expiry"]) / 1000, tz=timezone.utc).date()
                except (ValueError, TypeError):
                    expiry = None
            out.append(
                InstrumentDTO(
                    instrument_key=row["instrument_key"],
                    exchange=exch,
                    segment=segment,
                    instrument_type=itype,
                    tradingsymbol=row.get("trading_symbol") or row.get("tradingsymbol") or "",
                    name=row.get("name", ""),
                    category=classify_upstox(row),
                    isin=row.get("isin"),
                    lot_size=int(row.get("lot_size") or 1),
                    tick_size=Decimal(str(row.get("tick_size") or "0.05")),
                    freeze_qty=int(row["freeze_quantity"]) if row.get("freeze_quantity") else None,
                    expiry=expiry,
                    strike=Decimal(str(row["strike_price"])) if row.get("strike_price") else None,
                    underlying_key=row.get("underlying_key"),
                )
            )
        logger.info("Upstox instrument master: %d rows", len(out))
        return out

    async def subscribe(self, instrument_keys: list[str]) -> None:
        self._subscribed.update(instrument_keys)

    async def unsubscribe(self, instrument_keys: list[str]) -> None:
        self._subscribed.difference_update(instrument_keys)

    async def get_quote(self, instrument_keys: list[str]) -> dict[str, QuoteDTO]:
        if not instrument_keys:
            return {}
        out: dict[str, QuoteDTO] = {}
        # Upstox caps the query at ~500 instrument keys per call.
        for i in range(0, len(instrument_keys), 400):
            chunk = instrument_keys[i : i + 400]
            data = await self._get(
                "/market-quote/quotes", params={"instrument_key": ",".join(chunk)}
            )
            for _sym, q in (data.get("data") or {}).items():
                key = q.get("instrument_token") or q.get("instrument_key")
                if not key:
                    continue
                ohlc = q.get("ohlc") or {}
                ltp = Decimal(str(q.get("last_price") or 0))
                # previous close: net_change is authoritative (ohlc.close can equal
                # the live price during a session); fall back to ohlc.close
                prev = None
                if q.get("net_change") is not None:
                    prev = ltp - Decimal(str(q["net_change"]))
                elif ohlc.get("close"):
                    prev = Decimal(str(ohlc["close"]))
                out[key] = QuoteDTO(
                    instrument_key=key,
                    ltp=ltp,
                    prev_close=prev if prev and prev > 0 else None,
                    open=Decimal(str(ohlc.get("open"))) if ohlc.get("open") else None,
                    high=Decimal(str(ohlc.get("high"))) if ohlc.get("high") else None,
                    low=Decimal(str(ohlc.get("low"))) if ohlc.get("low") else None,
                    volume=int(q.get("volume") or 0),
                    oi=int(q.get("oi") or 0),
                    ts=datetime.now(timezone.utc),
                )
        return out

    async def stream(self) -> AsyncIterator[TickDTO]:
        while True:
            keys = list(self._subscribed)
            if keys:
                try:
                    quotes = await self.get_quote(keys)
                except UpstoxAuthError:
                    raise
                except httpx.HTTPError as exc:  # transient network issue — keep going
                    logger.warning("Upstox quote poll failed: %s", exc)
                    quotes = {}
                for q in quotes.values():
                    yield TickDTO(
                        instrument_key=q.instrument_key,
                        ltp=q.ltp,
                        ts=q.ts or datetime.now(timezone.utc),
                        prev_close=q.prev_close,
                        open=q.open,
                        volume=q.volume,
                        oi=q.oi,
                    )
            await asyncio.sleep(self._poll_interval)

    async def get_candles(
        self, instrument_key: str, interval: str, frm: datetime, to: datetime
    ) -> list[Candle]:
        """Historical candles + the in-progress session.

        Upstox's ``/historical-candle`` endpoint excludes the current day, so a
        daily chart otherwise ends at the last completed session. We fetch the
        intraday endpoint too and either merge it (minute intervals) or roll it
        into a synthetic bar for today (day/week/month).
        """
        to_d = to.date().isoformat()
        frm_d = frm.date().isoformat()
        hist_rows: list[list] = []
        try:
            hist = await self._get(
                f"/historical-candle/{instrument_key}/{interval}/{to_d}/{frm_d}"
            )
            hist_rows = hist.get("data", {}).get("candles", []) or []
        except httpx.HTTPStatusError as exc:
            logger.warning("historical-candle failed: %s", exc)

        intraday_iv = interval if interval in ("1minute", "30minute") else "1minute"
        intr_rows: list[list] = []
        try:
            intr = await self._get(
                f"/historical-candle/intraday/{instrument_key}/{intraday_iv}"
            )
            intr_rows = intr.get("data", {}).get("candles", []) or []
        except httpx.HTTPStatusError:
            pass

        if interval in ("1minute", "30minute"):
            merged = intr_rows + hist_rows  # both newest-first
        elif intr_rows:
            rows = list(reversed(intr_rows))  # oldest-first for the day
            day_ts = str(rows[0][0])[:10] + "T00:00:00+05:30"
            day_bar = [
                day_ts,
                float(rows[0][1]),
                max(float(r[2]) for r in rows),
                min(float(r[3]) for r in rows),
                float(rows[-1][4]),
                sum(int(r[5] or 0) for r in rows),
                0,
            ]
            merged = [day_bar] + hist_rows
        else:
            merged = hist_rows

        out: list[Candle] = []
        for c in merged:
            # [ts, open, high, low, close, volume, oi]
            out.append(
                Candle(
                    ts=datetime.fromisoformat(str(c[0])),
                    open=Decimal(str(c[1])),
                    high=Decimal(str(c[2])),
                    low=Decimal(str(c[3])),
                    close=Decimal(str(c[4])),
                    volume=int(c[5] or 0),
                    oi=int(c[6]) if len(c) > 6 else 0,
                )
            )

        # de-dupe (historical may already carry a partial "today"); newest wins
        by_key: dict = {}
        bucket_by_day = interval in ("day", "week", "month")
        for cc in sorted(out, key=lambda x: x.ts):
            by_key[cc.ts.date() if bucket_by_day else cc.ts] = cc
        return sorted(by_key.values(), key=lambda x: x.ts)

    async def get_option_chain(
        self, underlying_key: str, expiry: date
    ) -> list[OptionChainRow]:
        data = await self._get(
            "/option/chain",
            params={"instrument_key": underlying_key, "expiry_date": expiry.isoformat()},
        )
        rows: list[OptionChainRow] = []
        for item in data.get("data", []) or []:
            strike = Decimal(str(item.get("strike_price") or 0))
            call = item.get("call_options") or {}
            put = item.get("put_options") or {}
            cm = call.get("market_data") or {}
            pm = put.get("market_data") or {}
            rows.append(
                OptionChainRow(
                    strike=strike,
                    expiry=expiry,
                    call=QuoteDTO(
                        instrument_key=call.get("instrument_key", ""),
                        ltp=Decimal(str(cm.get("ltp") or 0)),
                    ),
                    put=QuoteDTO(
                        instrument_key=put.get("instrument_key", ""),
                        ltp=Decimal(str(pm.get("ltp") or 0)),
                    ),
                    call_oi=int(cm.get("oi") or 0),
                    put_oi=int(pm.get("oi") or 0),
                )
            )
        rows.sort(key=lambda r: r.strike)
        return rows

    async def aclose(self) -> None:
        await self._client.aclose()
