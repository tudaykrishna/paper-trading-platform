"""Phase 4: MIS square-off, T+1 holdings settlement."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Holding, Position
from app.models.enums import Product
from app.services import settlement
from app.services.execution.engine import process_tick

D = Decimal
RELIANCE = "NSE_EQ|INE002A01018"


async def _tick(db, key, ltp):
    n = await process_tick(db, key, D(str(ltp)))
    await db.commit()
    return n


@pytest.mark.asyncio
async def test_mis_square_off_flattens_position_and_releases_margin(
    client, auth, seeded_instruments, db
):
    h = auth["headers"]
    await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
              "product": "MIS", "order_type": "MARKET"},
        headers=h,
    )
    await _tick(db, RELIANCE, 2900)

    pos = (
        await db.execute(select(Position).where(Position.product == Product.MIS))
    ).scalar_one()
    assert pos.net_qty == 10
    assert pos.blocked_margin > 0
    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    assert D(funds["blocked_margin"]) > 0

    squared = await settlement.square_off_mis(db)
    await db.commit()
    assert squared == 1

    await db.refresh(pos)
    assert pos.net_qty == 0
    assert pos.blocked_margin == 0
    funds = (await client.get("/api/portfolio/funds", headers=h)).json()
    assert D(funds["blocked_margin"]) == 0


@pytest.mark.asyncio
async def test_square_off_endpoint_is_per_user(client, auth, seeded_instruments, db):
    h = auth["headers"]
    await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 5,
              "product": "MIS", "order_type": "MARKET"},
        headers=h,
    )
    await _tick(db, RELIANCE, 2900)
    resp = await client.post("/api/portfolio/square-off", headers=h)
    assert resp.status_code == 200
    assert resp.json()["squared_off"] == 1
    positions = (await client.get("/api/portfolio/positions", headers=h)).json()
    assert all(p["net_qty"] == 0 for p in positions)


@pytest.mark.asyncio
async def test_holdings_settle_t1(client, auth, seeded_instruments, db):
    h = auth["headers"]
    await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    await _tick(db, RELIANCE, 2900)

    holding = (await db.execute(select(Holding))).scalar_one()
    assert holding.qty == 10
    assert holding.settled_qty == 0

    settled = await settlement.settle_holdings_t1(db)
    await db.commit()
    assert settled == 1
    await db.refresh(holding)
    assert holding.settled_qty == 10
