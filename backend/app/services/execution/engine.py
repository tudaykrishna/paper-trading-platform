"""Tick-driven matching engine.

``process_tick`` is called once per instrument per tick. It loads that
instrument's resting orders, applies the fill rules, books fills through
``portfolio_service.apply_fill``, and publishes order/position updates.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Instrument, Order
from app.models.enums import OrderStatus, Product
from app.redis_client import (
    ORDER_UPDATES_CHANNEL,
    POSITION_UPDATES_CHANNEL,
    redis_client,
)
from app.services import portfolio_service, wallet_service

logger = logging.getLogger("engine")
D = Decimal


async def _publish(channel: str, payload: dict) -> None:
    try:
        await redis_client.publish(channel, json.dumps(payload, default=str))
    except Exception:  # noqa: BLE001 - engine must not die on a Redis hiccup
        pass


async def process_tick(
    db: AsyncSession,
    instrument_key: str,
    ltp: Decimal,
    *,
    bid: Decimal | None = None,
    ask: Decimal | None = None,
) -> int:
    """Match resting orders for one instrument against one tick. Returns #fills."""
    from app.services.execution.fills import decide_fill  # local import: pure module

    orders = (
        await db.execute(
            select(Order)
            .where(Order.instrument_key == instrument_key, Order.status == OrderStatus.OPEN)
            .order_by(Order.id)
        )
    ).scalars().all()
    if not orders:
        return 0

    instrument = (
        await db.execute(
            select(Instrument).where(Instrument.instrument_key == instrument_key)
        )
    ).scalar_one_or_none()
    if instrument is None:
        return 0

    fills = 0
    for order in orders:
        decision = decide_fill(
            order_type=order.order_type,
            side=order.side,
            limit_price=order.price,
            trigger_price=order.trigger_price,
            ltp=D(ltp),
            bid=D(bid) if bid is not None else None,
            ask=D(ask) if ask is not None else None,
            slippage_bps=settings.slippage_bps,
            triggered=order.triggered,
        )
        if decision.newly_triggered and not order.triggered:
            order.triggered = True
            await _publish(ORDER_UPDATES_CHANNEL, {**_order_payload(order), "event": "triggered"})
        fill_price = decision.fill_price
        if fill_price is None:
            continue

        remaining = order.qty - order.filled_qty
        if remaining <= 0:
            order.status = OrderStatus.COMPLETE
            continue

        try:
            trade = await portfolio_service.apply_fill(
                db, order, instrument, remaining, fill_price
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("fill failed for order %s: %s", order.id, exc)
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"fill error: {exc}"[:250]
            wallet = await wallet_service.get_wallet(db, order.user_id, for_update=True)
            await wallet_service.release_margin(db, wallet, order.blocked_margin)
            order.blocked_margin = D(0)
            await _publish(ORDER_UPDATES_CHANNEL, _order_payload(order))
            continue

        order.status = OrderStatus.COMPLETE
        fills += 1
        await _publish(ORDER_UPDATES_CHANNEL, {**_order_payload(order), "trade_id": trade.id,
                                               "fill_price": str(fill_price)})
        await _publish(POSITION_UPDATES_CHANNEL, {"user_id": order.user_id,
                                                  "instrument_key": instrument_key,
                                                  "product": order.product.value})
    await db.flush()
    return fills


def _order_payload(order: Order) -> dict:
    return {
        "user_id": order.user_id,
        "order_id": order.id,
        "instrument_key": order.instrument_key,
        "status": order.status.value,
        "side": order.side.value,
        "qty": order.qty,
        "filled_qty": order.filled_qty,
        "avg_fill_price": str(order.avg_fill_price) if order.avg_fill_price else None,
        "product": order.product.value,
    }
