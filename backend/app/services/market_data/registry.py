"""Select the configured market data provider."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.mock import MockProvider


@lru_cache
def get_provider() -> MarketDataProvider:
    provider = settings.market_data_provider.lower()
    if provider == "mock":
        return MockProvider()
    if provider == "upstox":
        from app.services.market_data.upstox import UpstoxProvider

        return UpstoxProvider()
    raise ValueError(f"unknown MARKET_DATA_PROVIDER: {settings.market_data_provider!r}")
