"""Required-margin approximation per product / segment.

This is a paper model, not SPAN:
- Equity CNC buy        -> full contract value
- Equity CNC sell       -> 0 (must be covered by holdings, checked at placement)
- Equity MIS            -> value / MIS_EQUITY_LEVERAGE
- Futures (FO/CDS/MCX)  -> FUT_MARGIN_PCT * notional
- Long option           -> full premium
- Short option          -> OPTION_SELL_MARGIN_PCT * (qty * strike), fallback premium * 10
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.config import settings
from app.models import Instrument
from app.models.enums import InstrumentType, Product, Side

D = Decimal


def _r(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def required_margin(
    instrument: Instrument,
    *,
    product: Product,
    side: Side,
    qty: int,
    price: Decimal,
) -> Decimal:
    """``qty`` is in units (already lot_size-expanded). ``price`` is per unit."""
    value = D(qty) * D(price)
    itype = instrument.instrument_type

    # Equity cash
    if product == Product.CNC:
        return _r(value) if side == Side.BUY else D(0)

    if product == Product.MIS and itype in (InstrumentType.EQUITY, InstrumentType.INDEX):
        lev = D(str(settings.mis_equity_leverage)) or D(1)
        return _r(value / lev)

    # Options
    if itype in (InstrumentType.CE, InstrumentType.PE):
        if side == Side.BUY:
            return _r(value)  # full premium
        base = instrument.strike if instrument.strike else price * 10
        return _r(D(qty) * D(base) * D(str(settings.option_sell_margin_pct)))

    # Futures (equity / index / currency / commodity)
    return _r(value * D(str(settings.fut_margin_pct)))
