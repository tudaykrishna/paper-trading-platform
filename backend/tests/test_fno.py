"""Phase 5: F&O — option chain, futures margin, option premium, expiry settlement."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.models import Instrument, Position
from app.models.enums import InstrumentType
from app.services import settlement
from app.services.execution.engine import process_tick

D = Decimal
NIFTY = "NSE_INDEX|Nifty 50"


async def _find(client, headers, q, itype):
    hits = (
        await client.get("/api/instruments/search", params={"q": q, "limit": 50}, headers=headers)
    ).json()
    for h in hits:
        if h["instrument_type"] == itype:
            return h
    raise AssertionError(f"no {itype} found for {q}: {[h['tradingsymbol'] for h in hits]}")


@pytest.mark.asyncio
async def test_option_chain_endpoint(client, auth, seeded_instruments):
    resp = await client.get(
        "/api/instruments/option-chain", params={"underlying_key": NIFTY}, headers=auth["headers"]
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 5
    assert all(r["call_key"] and r["put_key"] for r in rows)
    assert any(D(r["call_ltp"]) > 0 for r in rows)


@pytest.mark.asyncio
async def test_buy_nifty_future_blocks_pct_margin(client, auth, seeded_instruments, db):
    h = auth["headers"]
    fut = await _find(client, h, "NIFTY", "FUT")
    lot = fut["lot_size"]

    place = await client.post(
        "/api/orders",
        json={"instrument_key": fut["instrument_key"], "side": "BUY", "qty": lot,
              "product": "NRML", "order_type": "MARKET"},
        headers=h,
    )
    assert place.status_code == 201, place.text
    blocked = D(place.json()["blocked_margin"])
    assert blocked > 0

    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    # 20% margin => far less than the full notional
    assert D(funds["blocked_margin"]) == blocked
    assert D(funds["cash_balance"]) == D("1000000")   # cash untouched until fill (leveraged)

    ltp = D(
        (await client.get("/api/instruments/quote",
                          params={"keys": fut["instrument_key"]}, headers=h)).json()
        [fut["instrument_key"]]["ltp"]
    )
    await process_tick(db, fut["instrument_key"], ltp)
    await db.commit()

    positions = (await client.get("/api/portfolio/positions", headers=h)).json()
    assert len(positions) == 1
    assert positions[0]["net_qty"] == lot
    assert D(positions[0]["blocked_margin"]) > 0


@pytest.mark.asyncio
async def test_buy_option_debits_full_premium(client, auth, seeded_instruments, db):
    h = auth["headers"]
    ce = await _find(client, h, "NIFTY", "CE")
    lot = ce["lot_size"]
    premium = D(
        (await client.get("/api/instruments/quote",
                          params={"keys": ce["instrument_key"]}, headers=h)).json()
        [ce["instrument_key"]]["ltp"]
    )

    place = await client.post(
        "/api/orders",
        json={"instrument_key": ce["instrument_key"], "side": "BUY", "qty": lot,
              "product": "NRML", "order_type": "MARKET"},
        headers=h,
    )
    assert place.status_code == 201, place.text
    assert D(place.json()["blocked_margin"]) == (premium * lot).quantize(D("0.01"))

    await process_tick(db, ce["instrument_key"], premium)
    await db.commit()

    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    # premium paid (as position margin stays blocked) + charges out of cash
    assert D(funds["blocked_margin"]) > 0
    assert D(funds["cash_balance"]) < D("1000000")


@pytest.mark.asyncio
async def test_expiry_settlement_closes_position(client, auth, seeded_instruments, db):
    h = auth["headers"]
    ce = await _find(client, h, "NIFTY", "CE")
    lot = ce["lot_size"]
    premium = D(
        (await client.get("/api/instruments/quote",
                          params={"keys": ce["instrument_key"]}, headers=h)).json()
        [ce["instrument_key"]]["ltp"]
    )
    await client.post(
        "/api/orders",
        json={"instrument_key": ce["instrument_key"], "side": "BUY", "qty": lot,
              "product": "NRML", "order_type": "MARKET"},
        headers=h,
    )
    await process_tick(db, ce["instrument_key"], premium)
    await db.commit()

    # force the contract to have expired yesterday
    await db.execute(
        update(Instrument)
        .where(Instrument.instrument_key == ce["instrument_key"])
        .values(expiry=date.today() - timedelta(days=1))
    )
    await db.commit()

    n = await settlement.settle_expiries(db, on=date.today())
    await db.commit()
    assert n == 1

    positions = (await client.get("/api/portfolio/positions", headers=h)).json()
    assert all(p["net_qty"] == 0 for p in positions)
    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    assert D(funds["blocked_margin"]) == 0

    ledger = (await client.get("/api/portfolio/ledger", headers=h)).json()
    assert any(e["type"] == "SETTLEMENT" for e in ledger)
