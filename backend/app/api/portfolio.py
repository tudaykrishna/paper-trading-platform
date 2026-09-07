"""Funds, ledger, positions, holdings, and a portfolio summary."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.calendar import now_ist
from app.core.deps import CurrentUser, DbSession
from app.models import Holding, LedgerEntry, Position
from app.schemas.order import HoldingOut, PositionOut
from app.schemas.wallet import FundsOut, LedgerEntryOut
from app.services import market_service, settlement, wallet_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
D = Decimal


@router.get("/funds", response_model=FundsOut)
async def get_funds(user: CurrentUser, db: DbSession) -> FundsOut:
    wallet = await wallet_service.get_wallet(db, user.id)
    return FundsOut(
        cash_balance=wallet.cash_balance,
        blocked_margin=wallet.blocked_margin,
        available_cash=wallet.available_cash,
        opening_balance=wallet.opening_balance,
    )


@router.get("/ledger", response_model=list[LedgerEntryOut])
async def get_ledger(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[LedgerEntry]:
    wallet = await wallet_service.get_wallet(db, user.id)
    rows = (
        await db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.wallet_id == wallet.id)
            .order_by(LedgerEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows)


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(
    user: CurrentUser, db: DbSession, day: bool = Query(True)
) -> list[PositionOut]:
    stmt = select(Position).where(Position.user_id == user.id)
    if day:
        stmt = stmt.where(Position.trade_date == now_ist().date())
    rows = (await db.execute(stmt.order_by(Position.instrument_key))).scalars().all()

    quotes = await market_service.quotes_for([r.instrument_key for r in rows]) if rows else {}
    out: list[PositionOut] = []
    for r in rows:
        ltp = quotes[r.instrument_key].ltp if r.instrument_key in quotes else None
        unreal = None
        if ltp is not None and r.net_qty != 0:
            unreal = (D(ltp) - r.avg_price) * r.net_qty
        out.append(
            PositionOut(
                instrument_key=r.instrument_key,
                product=r.product,
                trade_date=r.trade_date,
                net_qty=r.net_qty,
                avg_price=r.avg_price,
                realized_pnl=r.realized_pnl,
                blocked_margin=r.blocked_margin,
                ltp=ltp,
                unrealized_pnl=unreal,
            )
        )
    return out


@router.get("/holdings", response_model=list[HoldingOut])
async def get_holdings(user: CurrentUser, db: DbSession) -> list[HoldingOut]:
    rows = (
        await db.execute(
            select(Holding).where(Holding.user_id == user.id, Holding.qty != 0)
            .order_by(Holding.instrument_key)
        )
    ).scalars().all()
    quotes = await market_service.quotes_for([r.instrument_key for r in rows]) if rows else {}
    out: list[HoldingOut] = []
    for r in rows:
        ltp = quotes[r.instrument_key].ltp if r.instrument_key in quotes else None
        cur = unreal = None
        if ltp is not None:
            cur = D(ltp) * r.qty
            unreal = (D(ltp) - r.avg_price) * r.qty
        out.append(
            HoldingOut(
                instrument_key=r.instrument_key,
                qty=r.qty,
                settled_qty=r.settled_qty,
                avg_price=r.avg_price,
                realized_pnl=r.realized_pnl,
                ltp=ltp,
                current_value=cur,
                unrealized_pnl=unreal,
            )
        )
    return out


@router.post("/square-off")
async def square_off_my_positions(user: CurrentUser, db: DbSession) -> dict:
    """Flatten all of my open intraday (MIS) positions at the last traded price."""
    n = await settlement.square_off_mis(db, user_id=user.id)
    return {"squared_off": n}


@router.get("/summary")
async def get_summary(user: CurrentUser, db: DbSession) -> dict:
    wallet = await wallet_service.get_wallet(db, user.id)
    positions = (
        await db.execute(
            select(Position).where(
                Position.user_id == user.id, Position.trade_date == now_ist().date()
            )
        )
    ).scalars().all()
    holdings = (
        await db.execute(
            select(Holding).where(Holding.user_id == user.id, Holding.qty != 0)
        )
    ).scalars().all()

    keys = [p.instrument_key for p in positions] + [h.instrument_key for h in holdings]
    quotes = await market_service.quotes_for(keys) if keys else {}

    day_realized = sum((p.realized_pnl for p in positions), D(0))
    day_unrealized = D(0)
    for p in positions:
        if p.net_qty and p.instrument_key in quotes:
            day_unrealized += (D(quotes[p.instrument_key].ltp) - p.avg_price) * p.net_qty

    holdings_value = D(0)
    holdings_unrealized = D(0)
    for h in holdings:
        if h.instrument_key in quotes:
            ltp = D(quotes[h.instrument_key].ltp)
            holdings_value += ltp * h.qty
            holdings_unrealized += (ltp - h.avg_price) * h.qty

    return {
        "cash_balance": str(wallet.cash_balance),
        "available_cash": str(wallet.available_cash),
        "blocked_margin": str(wallet.blocked_margin),
        "day_pnl": str(day_realized + day_unrealized),
        "day_realized_pnl": str(day_realized),
        "day_unrealized_pnl": str(day_unrealized),
        "holdings_value": str(holdings_value),
        "holdings_unrealized_pnl": str(holdings_unrealized),
    }
