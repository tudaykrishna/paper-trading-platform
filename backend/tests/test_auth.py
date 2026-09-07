"""Phase 1: registration, login, refresh, protected route."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_creates_user_and_wallet(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "trader@example.com", "password": "hunter2hunter2", "name": "Trader"},
    )
    assert resp.status_code == 201
    tokens = resp.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "trader@example.com"

    funds = await client.get(
        "/api/portfolio/funds", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert funds.status_code == 200
    body = funds.json()
    assert float(body["cash_balance"]) == 1_000_000.0
    assert float(body["available_cash"]) == 1_000_000.0


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "longpassword1", "name": "A"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "email_taken"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "correctpassword1", "name": "X"},
    )
    resp = await client.post(
        "/api/auth/login", json={"email": "x@example.com", "password": "wrongpassword1"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "r@example.com", "password": "refreshme12345", "name": "R"},
    )
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    # An access token must not be usable as a refresh token.
    bad = await client.post(
        "/api/auth/refresh", json={"refresh_token": reg.json()["access_token"]}
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401
