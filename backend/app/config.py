"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "dev"

    # Auth
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Database
    database_url: str = "postgresql+asyncpg://paper:paper@localhost:5432/paper_trading"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Wallet
    opening_balance: float = 1_000_000.0

    # Market data
    market_data_provider: str = "mock"
    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_redirect_uri: str = "http://localhost:8000/api/instruments/upstox/callback"
    upstox_access_token: str = ""

    # Execution engine
    slippage_bps: float = 0.0

    # Margin model (paper approximation — no real SPAN)
    mis_equity_leverage: float = 5.0     # intraday equity: margin = value / leverage
    fut_margin_pct: float = 0.20         # futures: margin = pct * notional
    option_sell_margin_pct: float = 0.15  # short option: pct * (qty * strike or underlying px)

    # Order validation
    enforce_market_hours: bool = False   # Phase 4 sets this True in deployment

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
