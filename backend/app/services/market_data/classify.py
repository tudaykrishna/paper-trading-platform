"""Classify a raw Upstox instrument-master row into an :class:`AssetCategory`.

The Upstox equity feed mixes real companies with thousands of closed-end mutual
fund / fixed-maturity / debt scheme rows (mostly on BSE). This uses the exchange
series/group code plus name keywords to separate them.
"""
from __future__ import annotations

import re

from app.models.enums import AssetCategory

# NSE "series" codes that are ordinary tradable equity.
_NSE_EQUITY_SERIES = {"EQ", "BE", "BZ", "BL", "IQ", "IL", "RL", "GC", "GB0"}
_NSE_SME_SERIES = {"SM", "ST", "SME"}
# NSE debt / g-sec / t-bill series (prefix match handles N0..N9, NA..NZ, Y*, Z*).
_NSE_BOND_SERIES = {"SG", "GS", "GB", "TB", "TF", "MF", "RR", "W1", "W3", "D1", "E1", "IV", "IF"}
_NSE_BOND_PREFIXES = ("N", "Y", "Z")

# BSE groups that can hold ordinary equity. Group F is ~always fund/debt schemes.
_BSE_EQUITY_GROUPS = {"A", "B", "T", "X", "XT", "M", "MT", "MS", "P", "E", "Z", "ZP", "W", "R"}

_MF_RE = re.compile(
    r"MUTUAL FUND|FIXED HORIZON|FIXED MATURITY|\bFMP\b|INTERVAL FUND|CAPITAL PROTECTION|"
    r"DUAL ADVANTAGE|HORIZON FUND|MONTHLY INCOME PLAN|\bMIP\b|INCOME FUND|LIQUID FUND|"
    r"SAVINGS FUND|HYBRID FUND|\bSERIES\b.*\bFUND\b|CLOSE ENDED|CLOSED ENDED",
    re.I,
)
_BOND_RE = re.compile(
    r"\bSDL\b|\bGOI\b|\bG-?SEC\b|\bGS\s?20\d\d\b|\bT-?BILL\b|\bNCD\b|DEBENTURE|\bBOND\b|"
    r"\bSLR\b|\d+(\.\d+)?%\s?20\d\d|GOVT\.? STOCK|GOVERNMENT STOCK|STRIPS",
    re.I,
)
_ETF_RE = re.compile(r"\bETF\b|BeES|\bBEES\b|GOLDBEES|LIQUIDBEES|INDEX FUND - ", re.I)
_REIT_RE = re.compile(r"\bREIT\b|\bINVIT\b|\bINVITS\b|INFRASTRUCTURE INVESTMENT TRUST|"
                      r"REAL ESTATE INVESTMENT TRUST", re.I)


def classify_upstox(row: dict) -> AssetCategory:
    seg = row.get("segment") or ""
    itype = (row.get("instrument_type") or "").upper()
    sec = (row.get("security_type") or "").upper()
    name = row.get("name") or ""
    symbol = row.get("trading_symbol") or row.get("tradingsymbol") or ""
    blob = f"{name} {symbol}"

    # index / non-equity segments — checked before the generic FUT branch so
    # a currency or commodity future lands in the right bucket
    if seg in ("NSE_INDEX", "BSE_INDEX", "GLOBAL_INDEX"):
        return AssetCategory.INDEX
    if itype in ("CE", "PE"):
        return AssetCategory.OPTION
    if seg in ("NCD_FO", "BCD_FO"):
        return AssetCategory.CURRENCY
    if seg in ("MCX_FO", "NSE_COM"):
        return AssetCategory.COMMODITY
    if itype == "FUT":
        return AssetCategory.FUTURE

    # equity-segment rows (NSE_EQ / BSE_EQ) — the messy bucket
    if _REIT_RE.search(blob):
        return AssetCategory.REIT_INVIT
    if _ETF_RE.search(blob):
        return AssetCategory.ETF
    if _MF_RE.search(blob):
        return AssetCategory.MUTUAL_FUND
    if _BOND_RE.search(blob):
        return AssetCategory.BOND
    if sec == "IPO":
        return AssetCategory.IPO

    if seg == "NSE_EQ":
        if itype in _NSE_SME_SERIES:
            return AssetCategory.SME
        if itype in _NSE_EQUITY_SERIES:
            return AssetCategory.EQUITY
        if itype in _NSE_BOND_SERIES or (itype[:1] in _NSE_BOND_PREFIXES and len(itype) == 2):
            return AssetCategory.BOND
        return AssetCategory.OTHER

    if seg == "BSE_EQ":
        if sec == "SME":
            return AssetCategory.SME
        if itype == "F":  # BSE 'F' group is fund / debt schemes
            return AssetCategory.MUTUAL_FUND
        if itype in _BSE_EQUITY_GROUPS:
            return AssetCategory.EQUITY
        return AssetCategory.OTHER

    return AssetCategory.OTHER
