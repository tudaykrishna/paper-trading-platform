"""Tradable instrument master, synced from the broker."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import AssetCategory, Exchange, InstrumentType, Segment
from app.models.mixins import PKMixin, TimestampMixin


class Instrument(Base, PKMixin, TimestampMixin):
    __tablename__ = "instruments"

    # Broker-native identifier, e.g. Upstox "NSE_EQ|INE002A01018".
    instrument_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    exchange: Mapped[Exchange] = mapped_column(Enum(Exchange, name="exchange"), nullable=False)
    segment: Mapped[Segment] = mapped_column(Enum(Segment, name="segment"), nullable=False)
    instrument_type: Mapped[InstrumentType] = mapped_column(
        Enum(InstrumentType, name="instrument_type"), nullable=False
    )
    # Search facet — kept as plain text (values from AssetCategory) so it can grow
    # without an ALTER TYPE and compares cleanly in ORDER BY CASE.
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AssetCategory.OTHER.value, index=True
    )
    tradingsymbol: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)

    lot_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0.05"))
    freeze_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Derivatives-only
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    underlying_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    __table_args__ = (
        Index("ix_instruments_segment_symbol", "segment", "tradingsymbol"),
    )
