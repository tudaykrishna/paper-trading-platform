"""Phase 3: pure position quantity math."""
from __future__ import annotations

from decimal import Decimal

from app.services.portfolio_service import apply_qty_math

D = Decimal


def test_averaging_up():
    m = apply_qty_math(100, D("100"), 100, D("110"))
    assert m.net_qty == 200
    assert m.avg_price == D("105")
    assert m.realized_delta == 0


def test_partial_close_realizes_pnl():
    m = apply_qty_math(200, D("105"), -50, D("120"))
    assert m.net_qty == 150
    assert m.avg_price == D("105")          # unchanged on reduce
    assert m.realized_delta == D("750")     # (120 - 105) * 50


def test_full_close_zeroes_avg():
    m = apply_qty_math(150, D("105"), -150, D("100"))
    assert m.net_qty == 0
    assert m.avg_price == 0
    assert m.realized_delta == D("-750")    # (100 - 105) * 150


def test_flip_through_zero():
    m = apply_qty_math(50, D("100"), -80, D("110"))
    assert m.net_qty == -30
    assert m.flipped is True
    assert m.avg_price == D("110")          # new short leg at fill price
    assert m.realized_delta == D("500")     # closed 50 @ (110 - 100)


def test_short_then_cover():
    opened = apply_qty_math(0, D("0"), -100, D("100"))
    assert opened.net_qty == -100 and opened.avg_price == D("100")
    covered = apply_qty_math(-100, D("100"), 100, D("90"))
    assert covered.net_qty == 0
    assert covered.realized_delta == D("1000")   # (90 - 100) * 100 * -1
