<div align="center">

<img src="frontend/src/assets/logo.png" width="88" alt="Paper Trading logo">

# Paper Trading Platform

**Trade the Indian markets with virtual money against a live feed.**

Full-stack trading simulator — a virtual wallet, a tick-driven execution engine,
equity + F&O + commodities, realistic charges, and a real-time UI.

<br>

![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React%2018-20232a?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-3178c6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169e1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker%20Compose-2496ed?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/backend%20tests-82%20passing-16a34a)

</div>

---

No real money and no real orders are ever involved. Users get a virtual cash
wallet and place **simulated** orders that fill against **live NSE/BSE market data
from the Upstox API** (or a built-in mock feed that needs no account). The
platform's job is everything *around* the feed:

- 🔐 accounts & JWT auth, virtual funds wallet with an **immutable ledger**
- 📈 full order lifecycle — **MARKET / LIMIT / SL / SL-M**, modify, cancel
- ⚙️ a **tick-driven execution simulator** that fills resting orders against live ticks
- 📊 positions, holdings, **T+1 settlement**, 15:15 MIS auto square-off
- 🧾 realistic statutory charges — brokerage, STT, exchange txn, SEBI, stamp, GST
- 🎯 **index F&O** with an option chain + expiry cash-settlement, currency & commodity futures
- 🏆 leaderboard, per-user account reset, light/dark theme + accent picker

> **Design:** the UI was mocked as a canvas first — see [`docs/DESIGN.md`](docs/DESIGN.md) and [`design/`](design/).

---

## ✨ Highlights

| | |
|---|---|
| **Permanent watchlist rail** | List tabs, search-and-add, inline Buy/Sell/chart/remove. It's the app's live-price engine. |
| **Real-time everywhere** | `/ws` streams ticks; every price page also polls every 4 s as a fallback. Only watchlisted + held instruments are fetched. |
| **IST-correct charts** | `lightweight-charts` with a live-updating last bar, daily bars keyed to the IST calendar date. |
| **Runs with zero setup** | `mock` provider = random-walk equities + synthetic NIFTY/BANKNIFTY chains + GOLDM/SILVERM/USDINR. No broker account. |
| **Pipeline health check** | `GET /api/debug/feed` — one unauthenticated call tells you if the feed is live. |

---

## 🚀 Quick start

```bash
cp .env.example .env            # set SECRET_KEY
docker compose up --build
```

- **App** → http://localhost:5173
- **API** → http://localhost:8000  ( `/docs` · `/health` · `/api/debug/feed` )

Register an account → you get **₹10,00,000** and a default *Popular* watchlist of
~20 large-caps + indices → start trading.

<details>
<summary><strong>Local dev without Docker for the backend</strong></summary>

```bash
docker compose up postgres redis          # infra only
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# optionally, in other terminals:
python -m app.workers.marketdata_main
python -m app.services.execution.worker
python -m app.workers.scheduler_main

cd ../frontend && cp .env.example .env && npm install && npm run dev
```

`ENV=dev` creates/repairs tables on API startup. For a real schema:
`cd backend && alembic upgrade head`.
</details>

---

## 🏗 Architecture

Four small processes share one codebase and talk over Redis.

```
                    ┌──────────────┐   REST poll
   Upstox API ──────▶  marketdata  │◀────────  watchlisted / held instruments only
                    └──────┬───────┘
                           │  Redis: quote:*  +  publish "ticks"
                           ▼
   ┌────────┐  WebSocket  ┌──────────┐   pub/sub    ┌──────────────────┐
   │ React  │◀───────────▶│   api    │◀────────────▶│      engine      │
   │  SPA   │   + REST     │ FastAPI  │              │ (order matching) │
   └────────┘             └────┬─────┘              └────────┬─────────┘
                               ▼                             ▼  fills / positions
                        ┌────────────┐                       │
                        │ PostgreSQL │◀──────────────────────┘
                        └────────────┘  ▲
                        ┌───────────────┴──┐
                        │    scheduler     │  08:00 sync · 15:15 square-off · 15:45 EOD
                        └──────────────────┘
```

| Process | Role |
|---|---|
| **api** | REST + WebSocket for the browser |
| **marketdata** | polls the provider, writes `quote:<key>` to Redis (180 s TTL), publishes each tick |
| **engine** | matches resting orders on each tick, books fills, settles the wallet |
| **scheduler** | instrument-master sync, MIS square-off, EOD (MTM + expiry settlement + T+1) |

---

## 🧰 Tech stack

| Layer | Tech |
|---|---|
| **Frontend** | React 18 · Vite · TypeScript · TanStack Query · Zustand · Tailwind · lightweight-charts · date-fns-tz |
| **Backend** | FastAPI (async) · SQLAlchemy 2.x · Alembic · APScheduler |
| **Data** | PostgreSQL (system of record) · Redis (ticks, pub/sub, cache) |
| **Auth** | JWT access/refresh · bcrypt |
| **Market data** | pluggable `MarketDataProvider` — `mock` or `upstox` |

---

## 🔑 Using real Upstox data

Default is `mock`. For live NSE/BSE data you need an Upstox account with API access:

1. Create an app at **account.upstox.com/developer/apps** with redirect URL
   `http://localhost:8000/api/instruments/upstox/callback`; copy the key + secret into `.env`.
2. Set `MARKET_DATA_PROVIDER=upstox`, `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`.
3. Generate a **daily access token** (Upstox tokens expire ~03:30 IST, no refresh token) — the
   OAuth code flow, then `POST /v2/login/authorization/token`. Put `access_token` in
   `.env` as `UPSTOX_ACCESS_TOKEN`.
4. `docker compose up -d --force-recreate marketdata api scheduler`

No auto-refresh: when the token expires the `marketdata` process logs a clear
message and exits. `backend/scripts/upstox_check.py` diagnoses token issues.

---

## 📁 Layout

```
backend/                     FastAPI app, 4 process entrypoints, Alembic, tests
  app/
    api/                     auth · instruments · watchlists · orders · portfolio
                             reports · leaderboard · account · debug · ws
    services/
      market_data/           MarketDataProvider ABC + mock + upstox + classify
      execution/             fill rules + matching engine + worker
      pricing/               charges.py (statutory + brokerage) · margin.py
      order_service · portfolio_service · settlement · ...
    models/  core/  schemas/  workers/
  scripts/upstox_check.py    standalone Upstox token / connectivity diagnostic
frontend/                    React + Vite SPA, nginx Dockerfile
  src/
    components/  pages/  store/ (auth · quotes · orderPad · chartFocus · theme)
    api/  lib/ (format · time)
design/                      the design-canvas sources (.dc.html + canvas.json + logo)
docs/DESIGN.md
```

---

## ✅ Tests

```bash
cd backend && pip install -e ".[dev]" && pytest      # 82 tests, throwaway SQLite
```

Covers auth, wallet/ledger, the charge & margin models, position math, fill rules
(incl. the SL latch), the order→engine→portfolio path, MIS square-off, T+1
settlement, F&O (futures margin, option premium, expiry cash-settlement),
instrument classification & search, the default-watchlist seed, and the leaderboard.

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` on 5432 / 6379 | `docker compose up postgres redis` |
| API 500s about missing columns | set `ENV=dev`, or `alembic upgrade head` |
| `marketdata` crash-loops | expired Upstox token — set `mock` or regenerate (`scripts/upstox_check.py`) |
| Prices frozen / % shows 0 | open `/api/debug/feed` — `channel_ticks_500ms > 0` means the feed is live |
| Watchlist empty after first run | click **Load popular list**, or `POST /api/watchlists/seed-popular` |

---

<div align="center"><sub>Paper trading only — not investment advice, and not connected to any real brokerage account.</sub></div>
