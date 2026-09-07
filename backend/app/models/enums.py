"""Domain enums shared across models, schemas, and services."""
from __future__ import annotations

import enum


class Exchange(str, enum.Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"      # NSE F&O
    BFO = "BFO"      # BSE F&O
    CDS = "CDS"      # currency derivatives
    MCX = "MCX"      # commodity


class Segment(str, enum.Enum):
    EQ = "EQ"        # equity cash
    FO = "FO"        # equity / index futures & options
    CDS = "CDS"      # currency futures & options
    MCX = "MCX"      # commodity futures & options


class InstrumentType(str, enum.Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    FUT = "FUT"
    CE = "CE"
    PE = "PE"


class AssetCategory(str, enum.Enum):
    """Coarse classification used for search facets and ranking."""

    EQUITY = "EQUITY"
    SME = "SME"
    ETF = "ETF"
    INDEX = "INDEX"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    MUTUAL_FUND = "MUTUAL_FUND"
    BOND = "BOND"
    REIT_INVIT = "REIT_INVIT"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    IPO = "IPO"
    OTHER = "OTHER"


# Lower = shown first in unfiltered search.
CATEGORY_RANK: dict[AssetCategory, int] = {
    AssetCategory.EQUITY: 0,
    AssetCategory.ETF: 1,
    AssetCategory.INDEX: 2,
    AssetCategory.FUTURE: 3,
    AssetCategory.OPTION: 4,
    AssetCategory.REIT_INVIT: 5,
    AssetCategory.SME: 6,
    AssetCategory.COMMODITY: 7,
    AssetCategory.CURRENCY: 8,
    AssetCategory.IPO: 9,
    AssetCategory.MUTUAL_FUND: 10,
    AssetCategory.BOND: 11,
    AssetCategory.OTHER: 12,
}


class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class Product(str, enum.Enum):
    CNC = "CNC"      # delivery (equity)
    MIS = "MIS"      # intraday, auto square-off
    NRML = "NRML"    # carry-forward derivatives


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"        # stop-loss limit
    SL_M = "SL-M"    # stop-loss market


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"        # accepted, not yet on the engine index
    OPEN = "OPEN"             # resting, awaiting fill
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Validity(str, enum.Enum):
    DAY = "DAY"
    IOC = "IOC"


class LedgerType(str, enum.Enum):
    DEPOSIT = "DEPOSIT"
    RESET = "RESET"
    FILL = "FILL"
    CHARGE = "CHARGE"
    MTM = "MTM"
    SETTLEMENT = "SETTLEMENT"
    MARGIN_BLOCK = "MARGIN_BLOCK"
    MARGIN_RELEASE = "MARGIN_RELEASE"
