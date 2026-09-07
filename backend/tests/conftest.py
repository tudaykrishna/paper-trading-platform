"""Test fixtures: isolated SQLite DB + ASGI client.

Env vars are set before any ``app.*`` import so the app builds its engine
against the throwaway database.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "paper_trading_test.sqlite3"
if _TMP_DB.exists():
    _TMP_DB.unlink()

os.environ.update(
    ENV="test",
    SECRET_KEY="test-secret-key-please-ignore",
    DATABASE_URL=f"sqlite+aiosqlite:///{_TMP_DB.as_posix()}",
    REDIS_URL="redis://localhost:6379/15",
    MARKET_DATA_PROVIDER="mock",
    OPENING_BALANCE="1000000",
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import app.models  # noqa: E402,F401  (register metadata first)
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402  (avoid shadowing the `app` package)
from app.redis_client import redis_client  # noqa: E402


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    """Tests run without a Redis server; make cache reads/writes harmless no-ops."""
    async def _none(*_a, **_k):
        return None

    monkeypatch.setattr(redis_client, "get", _none)
    monkeypatch.setattr(redis_client, "set", _none)
    monkeypatch.setattr(redis_client, "publish", _none)
    monkeypatch.setattr(redis_client, "ping", _none)


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    # fresh connection pool per test so no connection carries a stale
    # read-transaction snapshot across the test's separate sessions
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth(client):
    """Register a user and return {headers, user_id, tokens}."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "t@example.com", "password": "password12345", "name": "T"},
    )
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/api/auth/me", headers=headers)).json()
    return {"headers": headers, "user_id": me["id"], "tokens": tokens}


@pytest_asyncio.fixture
async def seeded_instruments(db):
    """Load the mock provider's universe into the instruments table."""
    from app.services import instrument_service
    from app.services.market_data.mock import MockProvider

    dtos = await MockProvider().instrument_master()
    await instrument_service.seed_from_dtos(db, dtos)
    await db.commit()
    return dtos
