"""Statutory + brokerage charge simulation for a single trade (one fill).

Rates follow the common Indian discount-broker model (post-Oct-2024 STT). They
live as named constants so they are easy to audit against a published brokerage
calculator. All returns are ``Decimal`` rupees, rounded to paise at the end.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import Exchange, InstrumentType, Product, Segment, Side

D = Decimal
Q = D("0.01")


def _r(x: Decimal) -> Decimal:
    return x.quantize(Q, rounding=ROUND_HALF_UP)


# ---- rate tables ---------------------------------------------------------------

BROKERAGE_FLAT = D("20")                 # per executed order, where a flat fee applies
BROKERAGE_PCT_INTRADAY = D("0.0005")     # 0.05% cap vs the flat fee (equity intraday)
BROKERAGE_PCT_FUT = D("0.0003")          # 0.03% cap vs the flat fee (futures)

STT = {
    "EQ_DELIVERY_BOTH": D("0.001"),      # 0.1% buy & sell
    "EQ_INTRADAY_SELL": D("0.00025"),    # 0.025% sell only
    "FUT_SELL": D("0.0002"),             # 0.02% sell only
    "OPT_SELL": D("0.001"),              # 0.1% of premium, sell only
}

# Exchange transaction charges (fraction of turnover / premium).
EXCH_TXN = {
    Segment.EQ: D("0.0000297"),
    Segment.FO: D("0.0000173"),          # futures
    "OPT": D("0.0003503"),               # options (of premium)
    Segment.CDS: D("0.00000900"),
    Segment.MCX: D("0.0000260"),
}

SEBI_CHARGES = D("0.000001")             # Rs 10 per crore
GST = D("0.18")                          # on brokerage + exch txn + SEBI

STAMP_DUTY_BUY = {                       # buy side only
    "EQ_DELIVERY": D("0.00015"),
    "EQ_INTRADAY": D("0.00003"),
    "FUT": D("0.00002"),
    "OPT": D("0.00003"),
    Segment.CDS: D("0.000001"),
    Segment.MCX: D("0.00001"),
}


@dataclass(slots=True)
class ChargeBreakdown:
    brokerage: Decimal = D(0)
    stt: Decimal = D(0)
    exchange_txn: Decimal = D(0)
    sebi: Decimal = D(0)
    stamp_duty: Decimal = D(0)
    gst: Decimal = D(0)

    @property
    def total(self) -> Decimal:
        return _r(
            self.brokerage + self.stt + self.exchange_txn + self.sebi + self.stamp_duty + self.gst
        )

    def as_dict(self) -> dict[str, str]:
        d = {k: str(_r(v)) for k, v in asdict(self).items()}
        d["total"] = str(self.total)
        return d


def compute_charges(
    *,
    segment: Segment,
    product: Product,
    side: Side,
    instrument_type: InstrumentType,
    qty: int,
    price: Decimal,
    exchange: Exchange = Exchange.NSE,
) -> ChargeBreakdown:
    turnover = D(qty) * D(price)
    is_buy = side == Side.BUY
    is_option = instrument_type in (InstrumentType.CE, InstrumentType.PE)
    b = ChargeBreakdown()

    # --- brokerage ---
    if segment == Segment.EQ:
        if product == Product.CNC:
            b.brokerage = D(0)
        else:  # MIS intraday
            b.brokerage = min(BROKERAGE_FLAT, turnover * BROKERAGE_PCT_INTRADAY)
    elif is_option:
        b.brokerage = BROKERAGE_FLAT
    else:  # futures (FO / CDS / MCX)
        b.brokerage = min(BROKERAGE_FLAT, turnover * BROKERAGE_PCT_FUT)

    # --- STT / CTT ---
    if segment == Segment.EQ:
        if product == Product.CNC:
            b.stt = turnover * STT["EQ_DELIVERY_BOTH"]
        elif not is_buy:
            b.stt = turnover * STT["EQ_INTRADAY_SELL"]
    elif is_option:
        if not is_buy:
            b.stt = turnover * STT["OPT_SELL"]
    else:  # futures
        if not is_buy:
            b.stt = turnover * STT["FUT_SELL"]

    # --- exchange transaction charges ---
    if is_option:
        b.exchange_txn = turnover * EXCH_TXN["OPT"]
    else:
        b.exchange_txn = turnover * EXCH_TXN.get(segment, EXCH_TXN[Segment.EQ])

    # --- SEBI turnover fees ---
    b.sebi = turnover * SEBI_CHARGES

    # --- stamp duty (buy side only) ---
    if is_buy:
        if segment == Segment.EQ:
            key = "EQ_DELIVERY" if product == Product.CNC else "EQ_INTRADAY"
            b.stamp_duty = turnover * STAMP_DUTY_BUY[key]
        elif is_option:
            b.stamp_duty = turnover * STAMP_DUTY_BUY["OPT"]
        elif segment == Segment.FO:
            b.stamp_duty = turnover * STAMP_DUTY_BUY["FUT"]
        else:
            b.stamp_duty = turnover * STAMP_DUTY_BUY.get(segment, D(0))

    # --- GST (on brokerage + exch txn + SEBI) ---
    b.gst = (b.brokerage + b.exchange_txn + b.sebi) * GST

    # round components
    b.brokerage = _r(b.brokerage)
    b.stt = _r(b.stt)
    b.exchange_txn = _r(b.exchange_txn)
    b.sebi = _r(b.sebi)
    b.stamp_duty = _r(b.stamp_duty)
    b.gst = _r(b.gst)
    return b
