"""Phase 3: charge simulation structure and sanity."""
from __future__ import annotations

from decimal import Decimal

from app.models.enums import Exchange, InstrumentType, Product, Side
from app.services.pricing.charges import compute_charges

D = Decimal


def _c(**kw):
    base = dict(
        segment=None, product=Product.CNC, side=Side.BUY,
        instrument_type=InstrumentType.EQUITY, qty=10, price=D("2900"),
        exchange=Exchange.NSE,
    )
    base.update(kw)
    return compute_charges(**base)


def test_equity_delivery_buy_has_stt_and_stamp_no_brokerage():
    from app.models.enums import Segment

    b = _c(segment=Segment.EQ, product=Product.CNC, side=Side.BUY)
    assert b.brokerage == 0
    assert b.stt > 0            # delivery STT on both sides
    assert b.stamp_duty > 0     # stamp on buy
    assert b.gst > 0
    assert b.total > 0


def test_equity_delivery_sell_has_stt_no_stamp():
    from app.models.enums import Segment

    b = _c(segment=Segment.EQ, product=Product.CNC, side=Side.SELL)
    assert b.stt > 0
    assert b.stamp_duty == 0    # stamp is buy-side only


def test_equity_intraday_brokerage_capped_at_20():
    from app.models.enums import Segment

    big = _c(segment=Segment.EQ, product=Product.MIS, side=Side.BUY, qty=1000, price=D("2900"))
    assert big.brokerage == D("20")
    small = _c(segment=Segment.EQ, product=Product.MIS, side=Side.BUY, qty=1, price=D("100"))
    assert small.brokerage < D("20")


def test_intraday_buy_has_no_stt_sell_does():
    from app.models.enums import Segment

    buy = _c(segment=Segment.EQ, product=Product.MIS, side=Side.BUY)
    sell = _c(segment=Segment.EQ, product=Product.MIS, side=Side.SELL)
    assert buy.stt == 0
    assert sell.stt > 0


def test_option_sell_stt_on_premium():
    from app.models.enums import Segment

    b = _c(segment=Segment.FO, product=Product.NRML, side=Side.SELL,
           instrument_type=InstrumentType.CE, qty=50, price=D("120"))
    assert b.brokerage == D("20")
    assert b.stt > 0
    total = b.total
    assert total == b.brokerage + b.stt + b.exchange_txn + b.sebi + b.stamp_duty + b.gst
