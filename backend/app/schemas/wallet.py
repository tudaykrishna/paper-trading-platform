"""Wallet / funds schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import LedgerType


class FundsOut(BaseModel):
    cash_balance: Decimal
    blocked_margin: Decimal
    available_cash: Decimal
    opening_balance: Decimal


class LedgerEntryOut(BaseModel):
    id: int
    ts: datetime
    type: LedgerType
    amount: Decimal
    balance_after: Decimal
    ref_order_id: int | None
    note: str | None

    model_config = {"from_attributes": True}
