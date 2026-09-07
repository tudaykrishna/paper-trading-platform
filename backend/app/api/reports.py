"""Realized P&L and charges reports, computed from the trade book."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.calendar import now_ist
from app.core.deps import CurrentUser, DbSession
from app.models import Trade

router = APIRouter(prefix="/api/reports", tags=["reports"])
D = Decimal


def _range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    today = now_ist().date()
    return (from_date or today - timedelta(days=30), to_date or today)


@router.get("/pnl")
async def pnl_report(
    user: CurrentUser,
    db: DbSession,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
) -> dict:
    frm, to = _range(from_date, to_date)
    trades = (
        await db.execute(
            select(Trade)
            .where(
                Trade.user_id == user.id,
                Trade.trade_date >= frm,
                Trade.trade_date <= to,
            )
            .order_by(Trade.ts)
        )
    ).scalars().all()

    by_day: dict[date, dict] = defaultdict(
        lambda: {"realized_pnl": D(0), "charges": D(0), "turnover": D(0), "trades": 0}
    )
    by_instrument: dict[str, dict] = defaultdict(
        lambda: {"realized_pnl": D(0), "charges": D(0), "turnover": D(0), "trades": 0}
    )
    tot_realized = tot_charges = tot_turnover = D(0)

    for t in trades:
        turnover = t.qty * t.price
        for bucket in (by_day[t.trade_date], by_instrument[t.instrument_key]):
            bucket["realized_pnl"] += t.realized_pnl
            bucket["charges"] += t.charges
            bucket["turnover"] += turnover
            bucket["trades"] += 1
        tot_realized += t.realized_pnl
        tot_charges += t.charges
        tot_turnover += turnover

    def _fmt(d: dict) -> dict:
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}

    return {
        "from": frm.isoformat(),
        "to": to.isoformat(),
        "totals": {
            "realized_pnl": str(tot_realized),
            "charges": str(tot_charges),
            "net_pnl": str(tot_realized - tot_charges),
            "turnover": str(tot_turnover),
            "trades": len(trades),
        },
        "by_day": [
            {"date": d.isoformat(), **_fmt(v)} for d, v in sorted(by_day.items())
        ],
        "by_instrument": [
            {"instrument_key": k, **_fmt(v)}
            for k, v in sorted(by_instrument.items(), key=lambda kv: kv[1]["realized_pnl"], reverse=True)
        ],
    }


@router.get("/charges")
async def charges_report(
    user: CurrentUser,
    db: DbSession,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
) -> dict:
    frm, to = _range(from_date, to_date)
    trades = (
        await db.execute(
            select(Trade).where(
                Trade.user_id == user.id,
                Trade.trade_date >= frm,
                Trade.trade_date <= to,
            )
        )
    ).scalars().all()

    heads = ("brokerage", "stt", "exchange_txn", "sebi", "stamp_duty", "gst")
    totals = {h: D(0) for h in heads}
    for t in trades:
        for h in heads:
            totals[h] += D(str(t.charges_breakdown.get(h, "0")))
    grand = sum(totals.values(), D(0))
    return {
        "from": frm.isoformat(),
        "to": to.isoformat(),
        "breakdown": {h: str(v) for h, v in totals.items()},
        "total": str(grand),
        "trades": len(trades),
    }
