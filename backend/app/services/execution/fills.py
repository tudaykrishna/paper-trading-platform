"""Pure fill-decision logic: given an order and the latest tick, would it fill,
and at what price? No I/O.

SL / SL-M orders latch: once the trigger is hit they behave as a plain
LIMIT / MARKET order even if price later moves back. The caller persists the
latch via ``Order.triggered`` and passes it back in as ``triggered``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import OrderType, Side

D = Decimal


@dataclass(slots=True)
class FillDecision:
    fill_price: Decimal | None = None
    newly_triggered: bool = False


def _slip(price: Decimal, side: Side, bps: float) -> Decimal:
    if not bps:
        return price
    factor = D(1) + (D(str(bps)) / D(10000)) * (D(1) if side == Side.BUY else D(-1))
    return (price * factor).quantize(D("0.01"))


def _limit_cross(side: Side, ltp: Decimal, lp: Decimal) -> Decimal | None:
    if side == Side.BUY and ltp <= lp:
        return min(lp, ltp)
    if side == Side.SELL and ltp >= lp:
        return max(lp, ltp)
    return None


def decide_fill(
    *,
    order_type: OrderType,
    side: Side,
    limit_price: Decimal | None,
    trigger_price: Decimal | None,
    ltp: Decimal,
    bid: Decimal | None = None,
    ask: Decimal | None = None,
    slippage_bps: float = 0.0,
    triggered: bool = False,
) -> FillDecision:
    ltp = D(ltp)

    if order_type == OrderType.MARKET:
        ref = (ask if side == Side.BUY else bid) or ltp
        return FillDecision(_slip(D(ref), side, slippage_bps))

    if order_type == OrderType.LIMIT:
        if limit_price is None:
            return FillDecision()
        return FillDecision(_limit_cross(side, ltp, D(limit_price)))

    if order_type in (OrderType.SL, OrderType.SL_M):
        if trigger_price is None:
            return FillDecision()
        tp = D(trigger_price)
        newly = False
        if not triggered:
            hit = (side == Side.BUY and ltp >= tp) or (side == Side.SELL and ltp <= tp)
            if not hit:
                return FillDecision()
            triggered = True
            newly = True

        if order_type == OrderType.SL_M:
            return FillDecision(_slip(ltp, side, slippage_bps), newly_triggered=newly)
        lp = D(limit_price) if limit_price is not None else tp
        return FillDecision(_limit_cross(side, ltp, lp), newly_triggered=newly)

    return FillDecision()
