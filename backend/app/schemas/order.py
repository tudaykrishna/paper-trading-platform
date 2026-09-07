"""Order + trade + position/holding schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OrderStatus, OrderType, Product, Side, Validity


class PlaceOrderRequest(BaseModel):
    instrument_key: str = Field(min_length=3, max_length=64)
    side: Side
    qty: int = Field(gt=0)
    product: Product
    order_type: OrderType
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    validity: Validity = Validity.DAY

    @model_validator(mode="after")
    def _check(self):
        if self.order_type in (OrderType.LIMIT, OrderType.SL) and self.price is None:
            raise ValueError("price is required for LIMIT / SL orders")
        if self.order_type in (OrderType.SL, OrderType.SL_M) and self.trigger_price is None:
            raise ValueError("trigger_price is required for SL / SL-M orders")
        return self


class ModifyOrderRequest(BaseModel):
    qty: int | None = Field(default=None, gt=0)
    price: Decimal | None = None
    trigger_price: Decimal | None = None


class OrderOut(BaseModel):
    id: int
    instrument_key: str
    side: Side
    qty: int
    product: Product
    order_type: OrderType
    validity: Validity
    price: Decimal | None
    trigger_price: Decimal | None
    status: OrderStatus
    filled_qty: int
    avg_fill_price: Decimal | None
    blocked_margin: Decimal
    reject_reason: str | None
    placed_at: datetime

    model_config = {"from_attributes": True}


class TradeOut(BaseModel):
    id: int
    order_id: int
    instrument_key: str
    side: Side
    qty: int
    price: Decimal
    charges: Decimal
    charges_breakdown: dict
    net_amount: Decimal
    ts: datetime
    trade_date: date

    model_config = {"from_attributes": True}


class PositionOut(BaseModel):
    instrument_key: str
    product: Product
    trade_date: date
    net_qty: int
    avg_price: Decimal
    realized_pnl: Decimal
    blocked_margin: Decimal
    ltp: Decimal | None = None
    unrealized_pnl: Decimal | None = None

    model_config = {"from_attributes": True}


class HoldingOut(BaseModel):
    instrument_key: str
    qty: int
    settled_qty: int
    avg_price: Decimal
    realized_pnl: Decimal
    ltp: Decimal | None = None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None

    model_config = {"from_attributes": True}
