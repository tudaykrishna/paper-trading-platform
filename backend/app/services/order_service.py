"""Order placement / modification / cancellation.

Placement validates, computes the margin the order needs *given the user's
current position* (a pure reduce needs none), blocks it, and persists the order
as OPEN. The execution engine picks it up on the next tick.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.calendar import is_market_open, now_ist
from app.core.exceptions import MarketClosedError, NotFoundError, ValidationError
from app.models import Holding, Instrument, Order, Position
from app.models.enums import OrderStatus, OrderType, Product, Side
from app.services import instrument_service, wallet_service
from app.services.pricing.margin import required_margin

D = Decimal


async def _current_net_qty(db: AsyncSession, user_id: int, key: str, product: Product) -> int:
    if product == Product.CNC:
        h = (
            await db.execute(
                select(Holding).where(Holding.user_id == user_id, Holding.instrument_key == key)
            )
        ).scalar_one_or_none()
        return h.qty if h else 0
    pos = (
        await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.instrument_key == key,
                Position.product == product,
                Position.trade_date == now_ist().date(),
            )
        )
    ).scalar_one_or_none()
    return pos.net_qty if pos else 0


async def _price_estimate(order_type: OrderType, price: Decimal | None,
                          trigger: Decimal | None, key: str) -> Decimal:
    if order_type in (OrderType.LIMIT, OrderType.SL) and price is not None:
        return D(price)
    if order_type == OrderType.SL_M and trigger is not None:
        return D(trigger)
    ltp = await instrument_service.last_price(key)
    if ltp is None:
        from app.services.market_service import quotes_for

        q = await quotes_for([key])
        if key in q and q[key].ltp:
            return D(q[key].ltp)
    if ltp is None:
        raise ValidationError("no live price available to size margin for this order")
    return D(ltp)


def _margin_for_intent(
    instrument: Instrument, side: Side, product: Product, qty: int, price: Decimal, net_qty: int
) -> Decimal:
    signed = qty if side == Side.BUY else -qty
    if product == Product.CNC and side == Side.SELL:
        return D(0)
    if net_qty == 0 or (net_qty > 0) == (signed > 0):
        return required_margin(instrument, product=product, side=side, qty=qty, price=price)
    # opposite side: reduce is free, only the flip portion needs margin
    if abs(signed) <= abs(net_qty):
        return D(0)
    flip_qty = abs(signed) - abs(net_qty)
    return required_margin(instrument, product=product, side=side, qty=flip_qty, price=price)


async def place_order(
    db: AsyncSession,
    user_id: int,
    *,
    instrument_key: str,
    side: Side,
    qty: int,
    product: Product,
    order_type: OrderType,
    price: Decimal | None,
    trigger_price: Decimal | None,
    validity,
) -> Order:
    instrument = await instrument_service.get_by_key(db, instrument_key)

    if instrument.lot_size > 1 and qty % instrument.lot_size != 0:
        raise ValidationError(
            f"qty must be a multiple of the lot size ({instrument.lot_size})"
        )
    if product == Product.NRML and instrument.segment.value == "EQ":
        raise ValidationError("NRML is not valid for equity cash — use CNC or MIS")
    if product == Product.CNC and instrument.segment.value != "EQ":
        raise ValidationError("CNC is only for equity cash")

    if settings.enforce_market_hours and not is_market_open(instrument.segment):
        raise MarketClosedError(f"{instrument.segment.value} market is closed right now")

    net_qty = await _current_net_qty(db, user_id, instrument_key, product)

    if product == Product.CNC and side == Side.SELL and qty > max(net_qty, 0):
        raise ValidationError(f"cannot sell {qty} — you hold {max(net_qty, 0)}")

    est = await _price_estimate(order_type, price, trigger_price, instrument_key)
    margin = _margin_for_intent(instrument, side, product, qty, est, net_qty)

    wallet = await wallet_service.get_wallet(db, user_id, for_update=True)
    if wallet.available_cash < margin:
        raise ValidationError(
            f"insufficient funds: need {margin}, have {wallet.available_cash} available",
            code="insufficient_funds",
        )
    await wallet_service.block_margin(db, wallet, margin)

    order = Order(
        user_id=user_id,
        instrument_key=instrument_key,
        side=side,
        qty=qty,
        product=product,
        order_type=order_type,
        validity=validity,
        price=D(price) if price is not None else None,
        trigger_price=D(trigger_price) if trigger_price is not None else None,
        status=OrderStatus.OPEN,
        blocked_margin=margin,
        placed_at=now_ist(),
    )
    db.add(order)
    await db.flush()
    return order


async def modify_order(
    db: AsyncSession, user_id: int, order_id: int,
    *, qty: int | None, price: Decimal | None, trigger_price: Decimal | None,
) -> Order:
    order = await _owned_open(db, user_id, order_id)
    if qty is not None:
        order.qty = qty
    if price is not None:
        order.price = D(price)
    if trigger_price is not None:
        order.trigger_price = D(trigger_price)

    instrument = await instrument_service.get_by_key(db, order.instrument_key)
    net_qty = await _current_net_qty(db, user_id, order.instrument_key, order.product)
    est = await _price_estimate(order.order_type, order.price, order.trigger_price, order.instrument_key)
    new_margin = _margin_for_intent(instrument, order.side, order.product, order.qty, est, net_qty)

    wallet = await wallet_service.get_wallet(db, user_id, for_update=True)
    delta = new_margin - order.blocked_margin
    if delta > 0:
        if wallet.available_cash < delta:
            raise ValidationError("insufficient funds to increase this order", code="insufficient_funds")
        await wallet_service.block_margin(db, wallet, delta)
    elif delta < 0:
        await wallet_service.release_margin(db, wallet, -delta)
    order.blocked_margin = new_margin
    await db.flush()
    return order


async def cancel_order(db: AsyncSession, user_id: int, order_id: int) -> Order:
    order = await _owned_open(db, user_id, order_id)
    wallet = await wallet_service.get_wallet(db, user_id, for_update=True)
    await wallet_service.release_margin(db, wallet, order.blocked_margin)
    order.blocked_margin = D(0)
    order.status = OrderStatus.CANCELLED
    await db.flush()
    return order


async def _owned_open(db: AsyncSession, user_id: int, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise NotFoundError("order not found")
    if order.status != OrderStatus.OPEN:
        raise ValidationError(f"order is {order.status.value}, cannot change it")
    return order
