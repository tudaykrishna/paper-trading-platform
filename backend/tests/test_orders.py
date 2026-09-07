"""Phase 3: order placement + engine fill + portfolio effects (equity CNC)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.execution.engine import process_tick

D = Decimal
RELIANCE = "NSE_EQ|INE002A01018"


async def _tick(db, key, ltp):
    n = await process_tick(db, key, D(str(ltp)))
    await db.commit()
    return n


@pytest.mark.asyncio
async def test_market_buy_fills_and_creates_holding(client, auth, seeded_instruments, db):
    h = auth["headers"]
    place = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    assert place.status_code == 201, place.text
    order = place.json()
    assert order["status"] == "OPEN"
    assert D(order["blocked_margin"]) > 0

    funds_before = (await client.get("/api/portfolio/funds", headers=h)).json()
    assert D(funds_before["blocked_margin"]) > 0

    assert await _tick(db, RELIANCE, 2900) == 1

    got = (await client.get(f"/api/orders/{order['id']}", headers=h)).json()
    assert got["status"] == "COMPLETE"
    assert got["filled_qty"] == 10

    holdings = (await client.get("/api/portfolio/holdings", headers=h)).json()
    assert len(holdings) == 1
    assert holdings[0]["instrument_key"] == RELIANCE
    assert holdings[0]["qty"] == 10

    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    assert D(funds["blocked_margin"]) == 0
    assert D(funds["cash_balance"]) < D("1000000")           # paid for shares + charges
    assert D(funds["cash_balance"]) > D("970000")

    trades = (await client.get("/api/orders/trades/book", headers=h)).json()
    assert len(trades) == 1
    assert D(trades[0]["charges"]) > 0


@pytest.mark.asyncio
async def test_limit_sell_closes_holding_and_realizes_pnl(client, auth, seeded_instruments, db):
    h = auth["headers"]
    await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    await _tick(db, RELIANCE, 2900)
    cash_after_buy = D((await client.get("/api/portfolio/funds", headers=h)).json()["cash_balance"])

    sell = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "SELL", "qty": 10,
              "product": "CNC", "order_type": "LIMIT", "price": "2950"},
        headers=h,
    )
    assert sell.status_code == 201
    # price below the limit -> stays open
    assert await _tick(db, RELIANCE, 2900) == 0
    got = (await client.get(f"/api/orders/{sell.json()['id']}", headers=h)).json()
    assert got["status"] == "OPEN"

    # price crosses the limit -> fills
    assert await _tick(db, RELIANCE, 2960) == 1
    got = (await client.get(f"/api/orders/{sell.json()['id']}", headers=h)).json()
    assert got["status"] == "COMPLETE"

    holdings = (await client.get("/api/portfolio/holdings", headers=h)).json()
    assert holdings == []
    cash_final = D((await client.get("/api/portfolio/funds", headers=h)).json()["cash_balance"])
    # sold 10 @ 2960 => ~29,600 back, minus charges; net well above the post-buy cash
    assert cash_final - cash_after_buy > D("29000")


@pytest.mark.asyncio
async def test_insufficient_funds_rejected(client, auth, seeded_instruments):
    h = auth["headers"]
    resp = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 1000,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "insufficient_funds"


@pytest.mark.asyncio
async def test_cancel_releases_margin(client, auth, seeded_instruments):
    h = auth["headers"]
    place = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 5,
              "product": "CNC", "order_type": "LIMIT", "price": "2800"},
        headers=h,
    )
    oid = place.json()["id"]
    assert D((await client.get("/api/portfolio/funds", headers=h)).json()["blocked_margin"]) > 0

    cancel = await client.request("DELETE", f"/api/orders/{oid}", headers=h)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELLED"
    assert D((await client.get("/api/portfolio/funds", headers=h)).json()["blocked_margin"]) == 0


@pytest.mark.asyncio
async def test_sell_more_than_held_rejected(client, auth, seeded_instruments):
    h = auth["headers"]
    resp = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "SELL", "qty": 5,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    assert resp.status_code == 422
