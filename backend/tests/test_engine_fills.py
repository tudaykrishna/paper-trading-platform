"""Phase 3: fill-decision rules."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.enums import OrderType, Side
from app.services.execution.fills import decide_fill

D = Decimal


def _f(**kw):
    base = dict(
        order_type=OrderType.MARKET, side=Side.BUY, limit_price=None,
        trigger_price=None, ltp=D("100"), bid=D("99.95"), ask=D("100.05"),
    )
    base.update(kw)
    return decide_fill(**base).fill_price


def test_market_buy_fills_at_ask():
    assert _f(order_type=OrderType.MARKET, side=Side.BUY) == D("100.05")


def test_market_sell_fills_at_bid():
    assert _f(order_type=OrderType.MARKET, side=Side.SELL) == D("99.95")


def test_limit_buy_only_fills_at_or_below_price():
    assert _f(order_type=OrderType.LIMIT, side=Side.BUY, limit_price=D("99"), ltp=D("100")) is None
    assert _f(order_type=OrderType.LIMIT, side=Side.BUY, limit_price=D("101"), ltp=D("100")) == D("100")


def test_limit_sell_only_fills_at_or_above_price():
    assert _f(order_type=OrderType.LIMIT, side=Side.SELL, limit_price=D("101"), ltp=D("100")) is None
    assert _f(order_type=OrderType.LIMIT, side=Side.SELL, limit_price=D("99"), ltp=D("100")) == D("100")


def test_sl_market_buy_triggers_when_price_rises_to_trigger():
    assert _f(order_type=OrderType.SL_M, side=Side.BUY, trigger_price=D("105"), ltp=D("104")) is None
    assert _f(order_type=OrderType.SL_M, side=Side.BUY, trigger_price=D("105"), ltp=D("106")) == D("106")


def test_sl_market_sell_triggers_when_price_falls_to_trigger():
    assert _f(order_type=OrderType.SL_M, side=Side.SELL, trigger_price=D("95"), ltp=D("96")) is None
    assert _f(order_type=OrderType.SL_M, side=Side.SELL, trigger_price=D("95"), ltp=D("94")) == D("94")


def test_sl_limit_latches_then_fills_as_limit():
    # trigger hit (ltp >= 105) but ltp 106 above the 103 limit -> latched, no fill yet
    first = decide_fill(order_type=OrderType.SL, side=Side.BUY, trigger_price=D("105"),
                        limit_price=D("103"), ltp=D("106"))
    assert first.fill_price is None
    assert first.newly_triggered is True
    # next tick: price back to 103, order already triggered -> fills at the limit
    second = decide_fill(order_type=OrderType.SL, side=Side.BUY, trigger_price=D("105"),
                         limit_price=D("103"), ltp=D("103"), triggered=True)
    assert second.fill_price == D("103")


def test_slippage_applied_to_market():
    px = _f(order_type=OrderType.MARKET, side=Side.BUY, bid=None, ask=None,
            ltp=D("100"), slippage_bps=50)
    assert px == D("100.50")
