"""Market session hours and holiday calendar (per segment).

Holidays are a static list refreshed manually each year — no reliable free API exists.
Times are IST (Asia/Kolkata).
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.models.enums import Segment

IST = ZoneInfo("Asia/Kolkata")

# Regular session windows per segment.
SESSIONS: dict[Segment, tuple[time, time]] = {
    Segment.EQ: (time(9, 15), time(15, 30)),
    Segment.FO: (time(9, 15), time(15, 30)),
    Segment.CDS: (time(9, 0), time(17, 0)),
    Segment.MCX: (time(9, 0), time(23, 30)),
}

# Intraday auto square-off cut-off (MIS).
SQUARE_OFF: dict[Segment, time] = {
    Segment.EQ: time(15, 15),
    Segment.FO: time(15, 15),
    Segment.CDS: time(16, 45),
    Segment.MCX: time(23, 15),
}

# NSE/BSE trading holidays. Extend per calendar year.
EQUITY_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 6),    # Holi
    date(2026, 3, 21),   # Id-ul-Fitr (tentative)
    date(2026, 4, 1),    # Annual bank closing
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 11, 9),   # Diwali (tentative)
    date(2026, 12, 25),  # Christmas
}

MCX_EXTRA_HOLIDAYS_2026: set[date] = set()


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def is_holiday(d: date, segment: Segment) -> bool:
    if d.weekday() >= 5:  # Sat/Sun
        return True
    if d in EQUITY_HOLIDAYS_2026:
        return True
    if segment == Segment.MCX and d in MCX_EXTRA_HOLIDAYS_2026:
        return True
    return False


def is_market_open(segment: Segment, at: datetime | None = None) -> bool:
    at = at or now_ist()
    at = at.astimezone(IST)
    if is_holiday(at.date(), segment):
        return False
    start, end = SESSIONS[segment]
    return start <= at.time() <= end
