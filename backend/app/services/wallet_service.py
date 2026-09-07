"""Virtual wallet operations. Every balance change writes an immutable ledger row.

All functions take an ``AsyncSession`` and flush but do NOT commit — the caller
owns the transaction boundary.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import InsufficientFundsError, NotFoundError
from app.models import LedgerEntry, Position, Wallet
from app.models.enums import LedgerType
from app.models.trading import Holding

D = Decimal


async def create_wallet(db: AsyncSession, user_id: int) -> Wallet:
    opening = D(str(settings.opening_balance))
    wallet = Wallet(
        user_id=user_id,
        cash_balance=opening,
        blocked_margin=D(0),
        opening_balance=opening,
    )
    db.add(wallet)
    await db.flush()
    db.add(
        LedgerEntry(
            wallet_id=wallet.id,
            type=LedgerType.DEPOSIT,
            amount=opening,
            balance_after=opening,
            note="Opening balance",
        )
    )
    await db.flush()
    return wallet


async def get_wallet(db: AsyncSession, user_id: int, *, for_update: bool = False) -> Wallet:
    stmt = select(Wallet).where(Wallet.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        raise NotFoundError("wallet not found")
    return wallet


async def _post(
    db: AsyncSession,
    wallet: Wallet,
    *,
    entry_type: LedgerType,
    amount: Decimal,
    ref_order_id: int | None = None,
    note: str | None = None,
) -> LedgerEntry:
    """Apply a signed amount to cash_balance and record it."""
    wallet.cash_balance = wallet.cash_balance + amount
    entry = LedgerEntry(
        wallet_id=wallet.id,
        type=entry_type,
        amount=amount,
        balance_after=wallet.cash_balance,
        ref_order_id=ref_order_id,
        note=note,
    )
    db.add(entry)
    await db.flush()
    return entry


async def block_margin(
    db: AsyncSession, wallet: Wallet, amount: Decimal, *, ref_order_id: int | None = None
) -> None:
    if amount <= 0:
        return
    if wallet.available_cash < amount:
        raise InsufficientFundsError(
            f"need {amount} but only {wallet.available_cash} available"
        )
    wallet.blocked_margin = wallet.blocked_margin + amount


async def release_margin(db: AsyncSession, wallet: Wallet, amount: Decimal) -> None:
    if amount <= 0:
        return
    wallet.blocked_margin = max(D(0), wallet.blocked_margin - amount)


async def apply_fill(
    db: AsyncSession,
    wallet: Wallet,
    *,
    gross: Decimal,
    charges: Decimal,
    released_margin: Decimal,
    ref_order_id: int,
    note: str,
) -> None:
    """Settle a fill: release blocked margin, move gross cash, debit charges.

    ``gross`` is signed from the wallet's perspective (negative when buying).
    """
    await release_margin(db, wallet, released_margin)
    if gross != 0:
        await _post(db, wallet, entry_type=LedgerType.FILL, amount=gross,
                    ref_order_id=ref_order_id, note=note)
    if charges > 0:
        await _post(db, wallet, entry_type=LedgerType.CHARGE, amount=-charges,
                    ref_order_id=ref_order_id, note=f"Charges: {note}")


async def adjust(
    db: AsyncSession,
    wallet: Wallet,
    *,
    amount: Decimal,
    entry_type: LedgerType,
    note: str,
    ref_order_id: int | None = None,
) -> None:
    """Generic signed adjustment (MTM, settlement)."""
    await _post(db, wallet, entry_type=entry_type, amount=amount,
               ref_order_id=ref_order_id, note=note)


async def reset_account(db: AsyncSession, user_id: int) -> Wallet:
    """Flatten positions/holdings and restore the wallet to its opening balance."""
    wallet = await get_wallet(db, user_id, for_update=True)
    await db.execute(delete(Position).where(Position.user_id == user_id))
    await db.execute(delete(Holding).where(Holding.user_id == user_id))

    wallet.cash_balance = wallet.opening_balance
    wallet.blocked_margin = D(0)
    db.add(
        LedgerEntry(
            wallet_id=wallet.id,
            type=LedgerType.RESET,
            amount=D(0),
            balance_after=wallet.opening_balance,
            note="Account reset to opening balance",
        )
    )
    await db.flush()
    return wallet
