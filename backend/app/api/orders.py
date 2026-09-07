"""Order book: place / modify / cancel / list, plus the trade book."""
from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError
from app.models import Order, Trade
from app.models.enums import OrderStatus
from app.schemas.order import (
    ModifyOrderRequest,
    OrderOut,
    PlaceOrderRequest,
    TradeOut,
)
from app.services import order_service

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(payload: PlaceOrderRequest, user: CurrentUser, db: DbSession) -> Order:
    return await order_service.place_order(
        db,
        user.id,
        instrument_key=payload.instrument_key,
        side=payload.side,
        qty=payload.qty,
        product=payload.product,
        order_type=payload.order_type,
        price=payload.price,
        trigger_price=payload.trigger_price,
        validity=payload.validity,
    )


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: CurrentUser,
    db: DbSession,
    open_only: bool = Query(False),
) -> list[Order]:
    stmt = select(Order).where(Order.user_id == user.id)
    if open_only:
        stmt = stmt.where(Order.status == OrderStatus.OPEN)
    stmt = stmt.order_by(Order.id.desc())
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, user: CurrentUser, db: DbSession) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise NotFoundError("order not found")
    return order


@router.put("/{order_id}", response_model=OrderOut)
async def modify_order(
    order_id: int, payload: ModifyOrderRequest, user: CurrentUser, db: DbSession
) -> Order:
    return await order_service.modify_order(
        db, user.id, order_id,
        qty=payload.qty, price=payload.price, trigger_price=payload.trigger_price,
    )


@router.delete("/{order_id}", response_model=OrderOut)
async def cancel_order(order_id: int, user: CurrentUser, db: DbSession) -> Order:
    return await order_service.cancel_order(db, user.id, order_id)


@router.get("/trades/book", response_model=list[TradeOut])
async def trade_book(user: CurrentUser, db: DbSession) -> list[Trade]:
    rows = (
        await db.execute(
            select(Trade).where(Trade.user_id == user.id).order_by(Trade.id.desc())
        )
    ).scalars().all()
    return list(rows)
