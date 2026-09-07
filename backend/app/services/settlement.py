"""End-of-day settlement: MIS square-off, T+1 holdings settlement, EOD snapshot.

Called by the scheduler. Each function takes a session and does NOT commit.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calendar import now_ist
from app.models import Holding, Instrument, Order, Position
from app.models.enums import (
    LedgerType,
    OrderStatus,
    OrderType,
    Product,
    Side,
    Validity,
)
from app.services import instrument_service, portfolio_service, wallet_service

logger = logging.getLogger("settlement")
D = Decimal


async def _square_off_price(instrument_key: str) -> Decimal | None:
    px = await instrument_service.last_price(instrument_key)
    if px is not None:
        return px
    try:
        from app.services.market_service import quotes_for

        q = await quotes_for([instrument_key])
        if instrument_key in q and q[instrument_key].ltp:
            return D(q[instrument_key].ltp)
    except Exception:  # noqa: BLE001
        pass
    return None


async def cancel_open_mis_orders(db: AsyncSession, *, user_id: int | None = None) -> int:
    """Cancel resting MIS orders and release their blocked margin."""
    stmt = select(Order).where(
        Order.status == OrderStatus.OPEN, Order.product == Product.MIS
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    orders = (await db.execute(stmt)).scalars().all()
    for o in orders:
        wallet = await wallet_service.get_wallet(db, o.user_id, for_update=True)
        await wallet_service.release_margin(db, wallet, o.blocked_margin)
        o.blocked_margin = D(0)
        o.status = OrderStatus.CANCELLED
        o.reject_reason = "auto-cancelled at MIS square-off"
    await db.flush()
    return len(orders)


async def square_off_mis(db: AsyncSession, *, user_id: int | None = None) -> int:
    """Flatten open intraday (MIS) positions with counter market fills.

    ``user_id`` limits it to one trader (used by the manual "square off" button);
    omitted, it flattens everyone (the 15:15 scheduler job).
    """
    await cancel_open_mis_orders(db, user_id=user_id)
    today = now_ist().date()
    stmt = select(Position).where(
        Position.product == Product.MIS,
        Position.trade_date == today,
        Position.net_qty != 0,
    )
    if user_id is not None:
        stmt = stmt.where(Position.user_id == user_id)
    positions = (await db.execute(stmt)).scalars().all()

    squared = 0
    for pos in positions:
        price = await _square_off_price(pos.instrument_key)
        if price is None:
            logger.warning("no price to square off %s for user %s", pos.instrument_key, pos.user_id)
            continue
        instrument = (
            await db.execute(
                select(Instrument).where(Instrument.instrument_key == pos.instrument_key)
            )
        ).scalar_one_or_none()
        if instrument is None:
            continue

        side = Side.SELL if pos.net_qty > 0 else Side.BUY
        qty = abs(pos.net_qty)
        counter = Order(
            user_id=pos.user_id,
            instrument_key=pos.instrument_key,
            side=side,
            qty=qty,
            product=Product.MIS,
            order_type=OrderType.MARKET,
            validity=Validity.DAY,
            status=OrderStatus.OPEN,
            blocked_margin=D(0),
            placed_at=now_ist(),
            reject_reason="auto square-off",
        )
        db.add(counter)
        await db.flush()
        await portfolio_service.apply_fill(db, counter, instrument, qty, price)
        counter.status = OrderStatus.COMPLETE
        squared += 1

    logger.info("MIS square-off: flattened %d position(s)", squared)
    return squared


async def settle_holdings_t1(db: AsyncSession) -> int:
    """Mark all held quantity as settled (paper T+1)."""
    result = await db.execute(
        update(Holding).where(Holding.qty != Holding.settled_qty).values(settled_qty=Holding.qty)
    )
    await db.flush()
    return result.rowcount or 0


async def mark_to_market_futures(db: AsyncSession) -> int:
    """Daily MTM on open futures positions: bank the day's move as cash and
    re-mark the position to the settlement (last) price."""
    from app.models.enums import InstrumentType

    positions = (
        await db.execute(
            select(Position).where(Position.net_qty != 0)
        )
    ).scalars().all()
    marked = 0
    for pos in positions:
        instrument = (
            await db.execute(
                select(Instrument).where(Instrument.instrument_key == pos.instrument_key)
            )
        ).scalar_one_or_none()
        if instrument is None or instrument.instrument_type != InstrumentType.FUT:
            continue
        settle = await _square_off_price(pos.instrument_key)
        if settle is None:
            continue
        mtm = (D(settle) - pos.avg_price) * pos.net_qty
        if mtm == 0:
            continue
        wallet = await wallet_service.get_wallet(db, pos.user_id, for_update=True)
        await wallet_service.adjust(
            db, wallet, amount=mtm, entry_type=LedgerType.MTM,
            note=f"MTM {instrument.tradingsymbol} @ {settle}",
        )
        pos.realized_pnl += mtm
        pos.avg_price = D(settle)
        marked += 1
    await db.flush()
    return marked


async def settle_expiries(db: AsyncSession, on: date | None = None) -> int:
    """Cash-settle every open F&O position whose contract has expired.

    Options settle at intrinsic value vs the underlying spot; futures settle at
    the underlying spot. The position is closed, margin released, and the P&L
    posted as a SETTLEMENT ledger entry.
    """
    from app.models.enums import InstrumentType

    on = on or now_ist().date()
    expired = (
        await db.execute(
            select(Instrument).where(
                Instrument.expiry.is_not(None), Instrument.expiry <= on
            )
        )
    ).scalars().all()
    expired_by_key = {i.instrument_key: i for i in expired}
    if not expired_by_key:
        return 0

    positions = (
        await db.execute(
            select(Position).where(
                Position.instrument_key.in_(expired_by_key), Position.net_qty != 0
            )
        )
    ).scalars().all()

    settled = 0
    for pos in positions:
        inst = expired_by_key[pos.instrument_key]
        spot = await _square_off_price(inst.underlying_key) if inst.underlying_key else None
        if spot is None:
            spot = await _square_off_price(pos.instrument_key)
        if spot is None:
            logger.warning("no spot to settle expired %s", pos.instrument_key)
            continue
        spot = D(spot)

        if inst.instrument_type == InstrumentType.CE:
            settle_px = max(D(0), spot - (inst.strike or D(0)))
        elif inst.instrument_type == InstrumentType.PE:
            settle_px = max(D(0), (inst.strike or D(0)) - spot)
        else:  # FUT
            settle_px = spot

        pnl = (settle_px - pos.avg_price) * pos.net_qty
        wallet = await wallet_service.get_wallet(db, pos.user_id, for_update=True)
        await wallet_service.release_margin(db, wallet, pos.blocked_margin)
        await wallet_service.adjust(
            db, wallet, amount=pnl, entry_type=LedgerType.SETTLEMENT,
            note=f"Expiry settlement {inst.tradingsymbol} @ {settle_px}",
        )
        pos.realized_pnl += pnl
        pos.net_qty = 0
        pos.avg_price = D(0)
        pos.blocked_margin = D(0)
        settled += 1

    logger.info("expiry settlement: closed %d position(s)", settled)
    await db.flush()
    return settled


async def run_eod(db: AsyncSession) -> dict:
    squared = await square_off_mis(db)
    marked = await mark_to_market_futures(db)
    expired = await settle_expiries(db)
    settled = await settle_holdings_t1(db)
    return {
        "mis_squared_off": squared,
        "futures_marked": marked,
        "expiries_settled": expired,
        "holdings_settled": settled,
        "date": now_ist().date().isoformat(),
    }
