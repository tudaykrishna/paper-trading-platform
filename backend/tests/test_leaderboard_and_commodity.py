"""Phase 6: leaderboard ranking + commodity/currency futures."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.execution.engine import process_tick

D = Decimal
RELIANCE = "NSE_EQ|INE002A01018"


async def _search_one(client, headers, q):
    hits = (await client.get("/api/instruments/search", params={"q": q}, headers=headers)).json()
    assert hits, f"no instrument for {q}"
    return hits[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol", ["GOLDM", "USDINR"])
async def test_commodity_and_currency_futures_are_tradable(
    client, auth, seeded_instruments, db, symbol
):
    h = auth["headers"]
    inst = await _search_one(client, h, symbol)
    key = inst["instrument_key"]

    place = await client.post(
        "/api/orders",
        json={"instrument_key": key, "side": "BUY", "qty": inst["lot_size"],
              "product": "MIS", "order_type": "MARKET"},
        headers=h,
    )
    assert place.status_code == 201, place.text
    assert D(place.json()["blocked_margin"]) > 0

    ltp = D(
        (await client.get("/api/instruments/quote", params={"keys": key}, headers=h)).json()
        [key]["ltp"]
    )
    await process_tick(db, key, ltp)
    await db.commit()

    positions = (await client.get("/api/portfolio/positions", headers=h)).json()
    assert any(p["instrument_key"] == key and p["net_qty"] == inst["lot_size"] for p in positions)


@pytest.mark.asyncio
async def test_leaderboard_ranks_by_pnl(client, seeded_instruments, db):
    async def _mk(email):
        r = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "password12345", "name": email[:4]},
        )
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    a = await _mk("a@example.com")
    b = await _mk("b@example.com")

    for h in (a, b):
        await client.post(
            "/api/orders",
            json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
                  "product": "CNC", "order_type": "MARKET"},
            headers=h,
        )
    await process_tick(db, RELIANCE, D("2900"))
    await db.commit()

    board = (await client.get("/api/leaderboard", headers=a)).json()
    assert len(board["rows"]) >= 2
    assert board["rows"][0]["rank"] == 1
    assert board["me"] is not None
    pnls = [D(r["pnl"]) for r in board["rows"]]
    assert pnls == sorted(pnls, reverse=True)
