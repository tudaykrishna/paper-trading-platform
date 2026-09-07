"""Phase 3: required-margin approximation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import Instrument
from app.models.enums import Exchange, InstrumentType, Product, Segment, Side
from app.services.pricing.margin import required_margin

D = Decimal


def _inst(**kw) -> Instrument:
    base = dict(
        instrument_key="X", exchange=Exchange.NSE, segment=Segment.EQ,
        instrument_type=InstrumentType.EQUITY, tradingsymbol="X", name="X",
        lot_size=1, tick_size=D("0.05"),
    )
    base.update(kw)
    return Instrument(**base)


def test_cnc_buy_needs_full_value():
    m = required_margin(_inst(), product=Product.CNC, side=Side.BUY, qty=10, price=D("2900"))
    assert m == D("29000.00")


def test_cnc_sell_needs_nothing():
    m = required_margin(_inst(), product=Product.CNC, side=Side.SELL, qty=10, price=D("2900"))
    assert m == 0


def test_mis_equity_is_leveraged():
    m = required_margin(_inst(), product=Product.MIS, side=Side.BUY, qty=10, price=D("2900"))
    assert m == D("5800.00")     # 29000 / 5


def test_futures_margin_is_pct_of_notional():
    fut = _inst(segment=Segment.FO, instrument_type=InstrumentType.FUT, lot_size=25)
    m = required_margin(fut, product=Product.NRML, side=Side.BUY, qty=25, price=D("20000"))
    assert m == D("100000.00")   # 500000 * 0.20


def test_long_option_is_full_premium():
    ce = _inst(segment=Segment.FO, instrument_type=InstrumentType.CE, lot_size=25,
               strike=D("20000"))
    m = required_margin(ce, product=Product.NRML, side=Side.BUY, qty=25, price=D("150"))
    assert m == D("3750.00")     # 25 * 150


def test_short_option_uses_strike_based_margin():
    ce = _inst(segment=Segment.FO, instrument_type=InstrumentType.CE, lot_size=25,
               strike=D("20000"))
    m = required_margin(ce, product=Product.NRML, side=Side.SELL, qty=25, price=D("150"))
    assert m == D("75000.00")    # 25 * 20000 * 0.15
