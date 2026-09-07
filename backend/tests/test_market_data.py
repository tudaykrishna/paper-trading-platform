"""Phase 2: instrument search, quotes, watchlists."""
from __future__ import annotations

import pytest

RELIANCE = "NSE_EQ|INE002A01018"
TCS = "NSE_EQ|INE467B01029"


@pytest.mark.asyncio
async def test_sync_instrument_master_bulk_insert(db):
    """Exercise the real delete + bulk-insert sync path (mock provider universe)."""
    from sqlalchemy import func, select

    from app.models import Instrument
    from app.services import instrument_service

    n = await instrument_service.sync_instrument_master(db)
    await db.commit()
    assert n > 8  # equity + index + futures + option chain
    count = (await db.execute(select(func.count(Instrument.id)))).scalar_one()
    assert count == n

    # idempotent — a second sync replaces, not duplicates
    n2 = await instrument_service.sync_instrument_master(db)
    await db.commit()
    count2 = (await db.execute(select(func.count(Instrument.id)))).scalar_one()
    assert count2 == n2 == n


@pytest.mark.asyncio
async def test_sync_endpoint(client, auth):
    resp = await client.post("/api/instruments/sync", headers=auth["headers"])
    assert resp.status_code == 200
    assert resp.json()["synced"] > 8
    hits = (
        await client.get("/api/instruments/search", params={"q": "NIFTY"}, headers=auth["headers"])
    ).json()
    assert hits


@pytest.mark.asyncio
async def test_instrument_search(client, auth, seeded_instruments):
    resp = await client.get("/api/instruments/search", params={"q": "REL"}, headers=auth["headers"])
    assert resp.status_code == 200
    hits = resp.json()
    assert any(h["tradingsymbol"] == "RELIANCE" for h in hits)


@pytest.mark.asyncio
async def test_quote_endpoint_uses_mock_provider(client, auth, seeded_instruments):
    resp = await client.get(
        "/api/instruments/quote", params={"keys": f"{RELIANCE},{TCS}"}, headers=auth["headers"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {RELIANCE, TCS}
    assert float(body[RELIANCE]["ltp"]) > 0


@pytest.mark.asyncio
async def test_default_watchlist_created_on_register(client, auth):
    resp = await client.get("/api/watchlists", headers=auth["headers"])
    assert resp.status_code == 200
    wls = resp.json()
    assert len(wls) == 1
    assert wls[0]["name"] == "Popular"


@pytest.mark.asyncio
async def test_default_watchlist_seeded_with_popular_instruments(client, auth):
    """When instruments are synced, a new user's default list is pre-populated."""
    await client.post("/api/instruments/sync", headers=auth["headers"])

    reg = await client.post(
        "/api/auth/register",
        json={"email": "seed@example.com", "password": "password12345", "name": "Seed"},
    )
    h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    wls = (await client.get("/api/watchlists", headers=h)).json()
    syms = {it["instrument"]["tradingsymbol"] for it in wls[0]["items"] if it["instrument"]}
    assert "RELIANCE" in syms and "TCS" in syms
    assert "NIFTY" in syms or "NIFTY 50" in syms  # index alias
    assert len(wls[0]["items"]) >= 8


@pytest.mark.asyncio
async def test_seed_popular_endpoint_backfills_existing_user(client, auth):
    before = (await client.get("/api/watchlists", headers=auth["headers"])).json()
    assert before[0]["items"] == []  # auth user registered before any instrument sync

    await client.post("/api/instruments/sync", headers=auth["headers"])
    seeded = (await client.post("/api/watchlists/seed-popular", headers=auth["headers"])).json()
    assert len(seeded[0]["items"]) >= 8

    again = (await client.post("/api/watchlists/seed-popular", headers=auth["headers"])).json()
    assert len(again[0]["items"]) == len(seeded[0]["items"])  # idempotent


@pytest.mark.asyncio
async def test_watchlist_add_remove_flow(client, auth, seeded_instruments):
    wl_id = (await client.get("/api/watchlists", headers=auth["headers"])).json()[0]["id"]

    add = await client.post(
        f"/api/watchlists/{wl_id}/items",
        json={"instrument_key": RELIANCE},
        headers=auth["headers"],
    )
    assert add.status_code == 200
    wl = add.json()
    assert len(wl["items"]) == 1
    assert wl["items"][0]["instrument_key"] == RELIANCE
    assert wl["items"][0]["instrument"]["tradingsymbol"] == "RELIANCE"
    assert float(wl["items"][0]["quote"]["ltp"]) > 0

    # idempotent add
    again = await client.post(
        f"/api/watchlists/{wl_id}/items", json={"instrument_key": RELIANCE}, headers=auth["headers"]
    )
    assert len(again.json()["items"]) == 1

    rem = await client.request(
        "DELETE", f"/api/watchlists/{wl_id}/items/{RELIANCE}", headers=auth["headers"]
    )
    assert rem.status_code == 200
    assert rem.json()["items"] == []


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client):
    assert (await client.get("/api/watchlists")).status_code == 401
