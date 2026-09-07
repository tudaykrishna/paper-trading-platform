"""Virtual wallet and its append-only ledger."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import LedgerType
from app.models.mixins import PKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

MONEY = Numeric(18, 4)


class Wallet(Base, PKMixin, TimestampMixin):
    __tablename__ = "wallets"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    cash_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    blocked_margin: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)

    user: Mapped["User"] = relationship(back_populates="wallet")
    entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan", order_by="LedgerEntry.id"
    )

    @property
    def available_cash(self) -> Decimal:
        return self.cash_balance - self.blocked_margin


class LedgerEntry(Base, PKMixin):
    __tablename__ = "ledger_entries"

    wallet_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("wallets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    type: Mapped[LedgerType] = mapped_column(Enum(LedgerType, name="ledger_type"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # signed: +credit / -debit
    balance_after: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    ref_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    wallet: Mapped["Wallet"] = relationship(back_populates="entries")
