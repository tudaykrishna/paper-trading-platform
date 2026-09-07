"""Turn a fill into a Trade + position/holding update + wallet settlement.

Position math is a pure helper (``apply_qty_math``) reused for both intraday
``positions`` and delivery ``holdings``. The engine calls :func:`apply_fill`
inside the caller's transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calendar import now_ist
from app.models import Holding, Instrument, Order, Position, Trade
from app.models.enums import LedgerType, Product, Side
from app.services import wallet_service
from app.services.pricing import margin as margin_calc
from app.services.pricing.charges import compute_charges

D = Decimal


@dataclass(slots=True)
class QtyMath:
    net_qty: int
    avg_price: Decimal
    realized_delta: Decimal
    closed_qty: int
    flipped: bool


def apply_qty_math(
    net_qty: int, avg_price: Decimal, signed_qty: int, price: Decimal
) -> QtyMath:
    """Apply ``signed_qty`` (buy > 0, sell < 0) @ ``price`` to an open position."""
    prev = net_qty
    new = prev + signed_qty
    realized = D(0)
    closed = 0
    flipped = False

    opening = prev == 0 or (prev > 0) == (signed_qty > 0)
    if opening:
        total = avg_price * abs(prev) + D(price) * abs(signed_qty)
        avg_price = (total / abs(new)) if new != 0 else D(0)
    else:
        closed = min(abs(prev), abs(signed_qty))
        sign = D(1) if prev > 0 else D(-1)
        realized = (D(price) - avg_price) * closed * sign
        if abs(signed_qty) > abs(prev):  # flipped through zero
            flipped = True
            avg_price = D(price)
        elif new == 0:
            avg_price = D(0)
    return QtyMath(net_qty=new, avg_price=avg_price, realized_delta=realized,
                   closed_qty=closed, flipped=flipped)


async def _get_or_create_position(
    db: AsyncSession, user_id: int, key: str, product: Product, d: date
) -> Position:
    pos = (
        await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.instrument_key == key,
                Position.product == product,
                Position.trade_date == d,
            )
        )
    ).scalar_one_or_none()
    if pos is None:
        pos = Position(
            user_id=user_id, instrument_key=key, product=product, trade_date=d,
            net_qty=0, avg_price=D(0), realized_pnl=D(0), blocked_margin=D(0),
        )
        db.add(pos)
        await db.flush()
    return pos


async def _get_or_create_holding(db: AsyncSession, user_id: int, key: str) -> Holding:
    h = (
        await db.execute(
            select(Holding).where(Holding.user_id == user_id, Holding.instrument_key == key)
        )
    ).scalar_one_or_none()
    if h is None:
        h = Holding(user_id=user_id, instrument_key=key, qty=0, settled_qty=0,
                    avg_price=D(0), realized_pnl=D(0))
        db.add(h)
        await db.flush()
    return h


async def apply_fill(
    db: AsyncSession, order: Order, instrument: Instrument, fill_qty: int, fill_price: Decimal
) -> Trade:
    """Book one fill. Mutates ``order``, position/holding, and the wallet."""
    today = now_ist().date()
    charges = compute_charges(
        segment=instrument.segment,
        product=order.product,
        side=order.side,
        instrument_type=instrument.instrument_type,
        qty=fill_qty,
        price=fill_price,
    )
    wallet = await wallet_service.get_wallet(db, order.user_id, for_update=True)
    signed = fill_qty if order.side == Side.BUY else -fill_qty
    turnover = D(fill_qty) * D(fill_price)
    net_cash = D(0)  # signed effect on cash before charges

    if order.product == Product.CNC:
        # cash-and-carry
        await wallet_service.release_margin(db, wallet, order.blocked_margin)
        h = await _get_or_create_holding(db, order.user_id, order.instrument_key)
        m = apply_qty_math(h.qty, h.avg_price, signed, fill_price)
        h.qty = m.net_qty
        h.avg_price = m.avg_price
        h.realized_pnl += m.realized_delta
        if order.side == Side.BUY:
            net_cash = -turnover
        else:
            net_cash = turnover
        await wallet_service.apply_fill(
            db, wallet, gross=net_cash, charges=charges.total, released_margin=D(0),
            ref_order_id=order.id,
            note=f"{order.side.value} {fill_qty} {instrument.tradingsymbol} CNC",
        )
    else:
        # leveraged (MIS / NRML): cash moves only by realized P&L + charges
        pos = await _get_or_create_position(db, order.user_id, order.instrument_key, order.product, today)
        prev = pos.net_qty
        m = apply_qty_math(prev, pos.avg_price, signed, fill_price)

        opening = prev == 0 or (prev > 0) == (signed > 0)
        if opening:
            pos.blocked_margin += order.blocked_margin  # keep block, attribute to position
        else:
            if prev != 0 and m.closed_qty:
                rel = (pos.blocked_margin * D(m.closed_qty) / abs(prev)).quantize(D("0.01"))
                pos.blocked_margin -= rel
                await wallet_service.release_margin(db, wallet, rel)
            await wallet_service.release_margin(db, wallet, order.blocked_margin)
            if m.flipped:
                new_leg = abs(m.net_qty)
                extra = margin_calc.required_margin(
                    instrument, product=order.product, side=order.side, qty=new_leg, price=fill_price
                )
                await wallet_service.block_margin(db, wallet, extra)
                pos.blocked_margin += extra

        pos.net_qty = m.net_qty
        pos.avg_price = m.avg_price
        pos.realized_pnl += m.realized_delta
        if order.side == Side.BUY:
            pos.buy_qty += fill_qty
            pos.buy_value += turnover
        else:
            pos.sell_qty += fill_qty
            pos.sell_value += turnover

        if m.realized_delta != 0:
            await wallet_service.adjust(
                db, wallet, amount=m.realized_delta, entry_type=LedgerType.FILL,
                note=f"Realized P&L {instrument.tradingsymbol}", ref_order_id=order.id,
            )
        await wallet_service.adjust(
            db, wallet, amount=-charges.total, entry_type=LedgerType.CHARGE,
            note=f"Charges: {order.side.value} {fill_qty} {instrument.tradingsymbol}",
            ref_order_id=order.id,
        )
        net_cash = m.realized_delta

    # order bookkeeping
    order.filled_qty += fill_qty
    prev_avg = order.avg_fill_price or D(0)
    prev_filled = order.filled_qty - fill_qty
    order.avg_fill_price = (
        (prev_avg * prev_filled + D(fill_price) * fill_qty) / order.filled_qty
    )

    trade = Trade(
        order_id=order.id,
        user_id=order.user_id,
        instrument_key=order.instrument_key,
        side=order.side,
        qty=fill_qty,
        price=D(fill_price),
        charges=charges.total,
        charges_breakdown=charges.as_dict(),
        realized_pnl=m.realized_delta,
        net_amount=net_cash - charges.total,
        trade_date=today,
    )
    db.add(trade)
    await db.flush()
    return trade


async def rebuild_positions_for_instrument(db: AsyncSession, user_id: int, instrument_key: str):
    """Replay trades to recompute a position (used after engine restart / audits)."""
    trades = (
        await db.execute(
            select(Trade)
            .where(Trade.user_id == user_id, Trade.instrument_key == instrument_key)
            .order_by(Trade.id)
        )
    ).scalars().all()
    return trades  # placeholder hook; positions are authoritative in this build
