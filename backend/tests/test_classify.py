"""Instrument classification + category-filtered search."""
from __future__ import annotations

import pytest

from app.models.enums import AssetCategory
from app.services.market_data.classify import classify_upstox


def _row(**kw):
    base = {"segment": "NSE_EQ", "instrument_type": "EQ", "security_type": "NORMAL",
            "name": "SOME COMPANY LTD", "trading_symbol": "SOMECO"}
    base.update(kw)
    return base


@pytest.mark.parametrize(
    "row, expected",
    [
        (_row(), AssetCategory.EQUITY),
        (_row(segment="BSE_EQ", instrument_type="A", name="RELIANCE INDUSTRIES LTD.",
              trading_symbol="RELIANCE"), AssetCategory.EQUITY),
        (_row(segment="BSE_EQ", instrument_type="F", name="RELIANCE MUTUAL FUND- RELIANCE",
              trading_symbol="NCAPBUILAD"), AssetCategory.MUTUAL_FUND),
        (_row(name="RELIANCE FIXED HORIZON FUND XXIV"), AssetCategory.MUTUAL_FUND),
        (_row(instrument_type="SG", name="SDL RJ 7.49% 2035"), AssetCategory.BOND),
        (_row(name="7.26% GS 2033"), AssetCategory.BOND),
        (_row(name="NIFTYBEES", trading_symbol="NIFTYBEES"), AssetCategory.ETF),
        (_row(name="NIPPON INDIA ETF NIFTY 50"), AssetCategory.ETF),
        (_row(name="EMBASSY OFFICE PARKS REIT"), AssetCategory.REIT_INVIT),
        (_row(name="IRB INVIT FUND"), AssetCategory.REIT_INVIT),
        (_row(instrument_type="SM", name="TINY SME LTD"), AssetCategory.SME),
        (_row(segment="NSE_INDEX", instrument_type="INDEX", name="Nifty 50"), AssetCategory.INDEX),
        (_row(segment="NSE_FO", instrument_type="FUT", name="NIFTY FUT"), AssetCategory.FUTURE),
        (_row(segment="NSE_FO", instrument_type="CE", name="NIFTY 24000 CE"), AssetCategory.OPTION),
        (_row(segment="MCX_FO", instrument_type="FUT", name="GOLD"), AssetCategory.COMMODITY),
        (_row(segment="NCD_FO", instrument_type="FUT", name="USDINR"), AssetCategory.CURRENCY),
        (_row(security_type="IPO", name="NEW CO LTD"), AssetCategory.IPO),
    ],
)
def test_classify_upstox(row, expected):
    assert classify_upstox(row) == expected


@pytest.mark.asyncio
async def test_search_category_filter_and_ranking(client, auth, db):
    """Mock universe: stocks are EQUITY, index is INDEX, options are OPTION."""
    from app.services import instrument_service

    await instrument_service.sync_instrument_master(db)
    await db.commit()
    h = auth["headers"]

    stocks = (
        await client.get(
            "/api/instruments/search", params={"q": "R", "category": "EQUITY"}, headers=h
        )
    ).json()
    assert stocks and all(s["category"] == "EQUITY" for s in stocks)

    opts = (
        await client.get(
            "/api/instruments/search", params={"q": "NIFTY", "category": "OPTION"}, headers=h
        )
    ).json()
    assert opts and all(o["category"] == "OPTION" for o in opts)

    # exact symbol match ranks first
    reliance = (
        await client.get("/api/instruments/search", params={"q": "RELIANCE"}, headers=h)
    ).json()
    assert reliance[0]["tradingsymbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_categories_endpoint(client, auth):
    cats = (await client.get("/api/instruments/categories", headers=auth["headers"])).json()
    assert "EQUITY" in cats and "MUTUAL_FUND" in cats and "BOND" in cats
