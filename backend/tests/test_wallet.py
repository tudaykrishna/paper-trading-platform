"""Phase 1: wallet service — opening balance, margin, ledger, reset."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import InsufficientFundsError
from app.models import LedgerEntry, Position, User
from app.models.enums import LedgerType, Product
from app.services import wallet_service

D = Decimal


async def _make_user(db, email="w@example.com") -> User:
    user = User(email=email, password_hash="x", name="W")
    db.add(user)
    await db.flush()
    await wallet_service.create_wallet(db, user.id)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_create_wallet_sets_opening_balance_and_ledger(db):
    user = await _make_user(db)
    wallet = await wallet_service.get_wallet(db, user.id)
    assert wallet.cash_balance == D("1000000")
    assert wallet.opening_balance == D("1000000")
    assert wallet.available_cash == D("1000000")

    entries = (
        await db.execute(select(LedgerEntry).where(LedgerEntry.wallet_id == wallet.id))
    ).scalars().all()
    assert len(entries) == 1
    assert entries[0].type == LedgerType.DEPOSIT
    assert entries[0].balance_after == D("1000000")


@pytest.mark.asyncio
async def test_block_and_release_margin(db):
    user = await _make_user(db)
    wallet = await wallet_service.get_wallet(db, user.id, for_update=True)

    await wallet_service.block_margin(db, wallet, D("250000"))
    assert wallet.blocked_margin == D("250000")
    assert wallet.available_cash == D("750000")

    await wallet_service.release_margin(db, wallet, D("100000"))
    assert wallet.blocked_margin == D("150000")
    assert wallet.available_cash == D("850000")


@pytest.mark.asyncio
async def test_block_margin_insufficient_funds(db):
    user = await _make_user(db)
    wallet = await wallet_service.get_wallet(db, user.id, for_update=True)
    with pytest.raises(InsufficientFundsError):
        await wallet_service.block_margin(db, wallet, D("2000000"))


@pytest.mark.asyncio
async def test_apply_fill_moves_cash_and_records_charges(db):
    user = await _make_user(db)
    wallet = await wallet_service.get_wallet(db, user.id, for_update=True)
    await wallet_service.block_margin(db, wallet, D("290000"))

    # Buy 100 @ 2900 => -290000 gross, 25 charges, release the 290000 block.
    await wallet_service.apply_fill(
        db, wallet,
        gross=D("-290000"), charges=D("25"), released_margin=D("290000"),
        ref_order_id=1, note="BUY 100 RELIANCE",
    )
    assert wallet.blocked_margin == D("0")
    assert wallet.cash_balance == D("709975")

    types = [
        e.type
        for e in (
            await db.execute(
                select(LedgerEntry).where(LedgerEntry.wallet_id == wallet.id).order_by(LedgerEntry.id)
            )
        ).scalars().all()
    ]
    assert types == [LedgerType.DEPOSIT, LedgerType.FILL, LedgerType.CHARGE]


@pytest.mark.asyncio
async def test_reset_account_restores_balance_and_flattens(db):
    user = await _make_user(db)
    wallet = await wallet_service.get_wallet(db, user.id, for_update=True)
    await wallet_service.apply_fill(
        db, wallet, gross=D("-500000"), charges=D("100"), released_margin=D("0"),
        ref_order_id=1, note="buy",
    )
    db.add(
        Position(
            user_id=user.id, instrument_key="NSE_EQ|X", product=Product.MIS,
            trade_date=__import__("datetime").date.today(), net_qty=10, avg_price=D("100"),
        )
    )
    await db.commit()

    wallet = await wallet_service.reset_account(db, user.id)
    await db.commit()

    assert wallet.cash_balance == D("1000000")
    assert wallet.blocked_margin == D("0")
    positions = (
        await db.execute(select(Position).where(Position.user_id == user.id))
    ).scalars().all()
    assert positions == []
