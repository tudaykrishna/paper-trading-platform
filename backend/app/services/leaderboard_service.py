"""Rank traders by net worth vs their opening balance.

net_worth = cash_balance + holdings market value + open-position unrealized P&L
(``cash_balance`` already includes any blocked margin).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Holding, Position, User, Wallet
from app.services import market_service

D = Decimal


async def compute(db: AsyncSession, limit: int = 50) -> list[dict]:
    wallets = (
        await db.execute(select(Wallet, User.name).join(User, User.id == Wallet.user_id))
    ).all()
    holdings = (await db.execute(select(Holding).where(Holding.qty != 0))).scalars().all()
    positions = (await db.execute(select(Position).where(Position.net_qty != 0))).scalars().all()

    keys = {h.instrument_key for h in holdings} | {p.instrument_key for p in positions}
    quotes = await market_service.quotes_for(list(keys)) if keys else {}

    h_by_user: dict[int, Decimal] = {}
    for h in holdings:
        if h.instrument_key in quotes:
            h_by_user[h.user_id] = h_by_user.get(h.user_id, D(0)) + D(quotes[h.instrument_key].ltp) * h.qty

    p_by_user: dict[int, Decimal] = {}
    for p in positions:
        if p.instrument_key in quotes:
            unreal = (D(quotes[p.instrument_key].ltp) - p.avg_price) * p.net_qty
            p_by_user[p.user_id] = p_by_user.get(p.user_id, D(0)) + unreal

    rows: list[dict] = []
    for wallet, name in wallets:
        net_worth = wallet.cash_balance + h_by_user.get(wallet.user_id, D(0)) + p_by_user.get(
            wallet.user_id, D(0)
        )
        opening = wallet.opening_balance or D(1)
        pnl = net_worth - opening
        rows.append(
            {
                "user_id": wallet.user_id,
                "name": name,
                "net_worth": str(net_worth.quantize(D("0.01"))),
                "pnl": str(pnl.quantize(D("0.01"))),
                "return_pct": str((pnl / opening * 100).quantize(D("0.01"))),
            }
        )

    rows.sort(key=lambda r: Decimal(r["pnl"]), reverse=True)
    for i, r in enumerate(rows[:limit], start=1):
        r["rank"] = i
    return rows[:limit]
