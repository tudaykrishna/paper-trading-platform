"""Watchlists, orders, trades, positions, holdings."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

# JSONB on Postgres, plain JSON elsewhere (tests on SQLite).
JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")

from app.db import Base
from app.models.enums import (
    OrderStatus,
    OrderType,
    Product,
    Side,
    Validity,
)
from app.models.mixins import PKMixin, TimestampMixin

MONEY = Numeric(18, 4)
PRICE = Numeric(14, 4)


class Watchlist(Base, PKMixin, TimestampMixin):
    __tablename__ = "watchlists"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="My Watchlist")

    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", order_by="WatchlistItem.position"
    )


class WatchlistItem(Base, PKMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "instrument_key", name="uq_watchlist_instrument"),)

    watchlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("watchlists.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument_key: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")


class Order(Base, PKMixin, TimestampMixin):
    __tablename__ = "orders"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    side: Mapped[Side] = mapped_column(Enum(Side, name="side"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)  # absolute quantity in units
    product: Mapped[Product] = mapped_column(Enum(Product, name="product"), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType, name="order_type"), nullable=False)
    validity: Mapped[Validity] = mapped_column(
        Enum(Validity, name="validity"), nullable=False, default=Validity.DAY
    )

    price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)          # limit price
    trigger_price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)  # SL trigger

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.PENDING, index=True
    )
    filled_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(PRICE, nullable=True)
    triggered: Mapped[bool] = mapped_column(default=False, nullable=False)  # SL/SL-M latch
    blocked_margin: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    parent_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    trades: Mapped[list["Trade"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Trade.id"
    )


class Trade(Base, PKMixin):
    __tablename__ = "trades"

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    side: Mapped[Side] = mapped_column(Enum(Side, name="side"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    charges: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    charges_breakdown: Mapped[dict] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    # Realized P&L booked by this fill (0 for pure opens), gross of charges.
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    # Signed cash effect on the wallet including charges (negative = cash out).
    net_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    order: Mapped["Order"] = relationship(back_populates="trades")


class Position(Base, PKMixin, TimestampMixin):
    """Intraday / derivatives net position, keyed per trading day + product."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "instrument_key", "product", "trade_date", name="uq_position_key"
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    product: Mapped[Product] = mapped_column(Enum(Product, name="product"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    net_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # signed
    avg_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    blocked_margin: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    buy_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sell_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buy_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    sell_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)


class Holding(Base, PKMixin, TimestampMixin):
    """Delivery (CNC) equity holding, netted across days with T+1 settlement."""

    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("user_id", "instrument_key", name="uq_holding_key"),)

    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    instrument_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settled_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
