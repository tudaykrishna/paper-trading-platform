"""Phase 4: market-hours enforcement in order validation + reports smoke."""
from __future__ import annotations

from datetime import date

import pytest

from app.core.calendar import is_holiday, is_market_open
from app.models.enums import Segment

RELIANCE = "NSE_EQ|INE002A01018"


def test_weekend_is_a_holiday():
    assert is_holiday(date(2026, 1, 3), Segment.EQ)   # Saturday
    assert is_holiday(date(2026, 1, 4), Segment.EQ)   # Sunday


def test_known_nse_holiday():
    assert is_holiday(date(2026, 1, 26), Segment.EQ)  # Republic Day


def test_mcx_open_later_than_equity():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    at = datetime(2026, 1, 5, 20, 0, tzinfo=ist)  # Monday 20:00
    assert is_market_open(Segment.MCX, at) is True
    assert is_market_open(Segment.EQ, at) is False


@pytest.mark.asyncio
async def test_order_rejected_when_market_closed(client, auth, seeded_instruments, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "enforce_market_hours", True)
    monkeypatch.setattr("app.services.order_service.is_market_open", lambda *_a, **_k: False)

    resp = await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 1,
              "product": "CNC", "order_type": "MARKET"},
        headers=auth["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "market_closed"


@pytest.mark.asyncio
async def test_pnl_and_charges_reports(client, auth, seeded_instruments, db):
    from decimal import Decimal

    from app.services.execution.engine import process_tick

    h = auth["headers"]
    await client.post(
        "/api/orders",
        json={"instrument_key": RELIANCE, "side": "BUY", "qty": 10,
              "product": "CNC", "order_type": "MARKET"},
        headers=h,
    )
    await process_tick(db, RELIANCE, Decimal("2900"))
    await db.commit()

    pnl = (await client.get("/api/reports/pnl", headers=h)).json()
    assert pnl["totals"]["trades"] == 1
    assert Decimal(pnl["totals"]["charges"]) > 0
    assert len(pnl["by_day"]) == 1

    charges = (await client.get("/api/reports/charges", headers=h)).json()
    assert charges["trades"] == 1
    assert Decimal(charges["total"]) > 0
    assert Decimal(charges["breakdown"]["stt"]) > 0
