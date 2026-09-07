# Paper Trading Platform

A **paper (virtual) trading application** for the Indian markets. Users get a
virtual cash wallet and place **simulated** orders that are filled against **live
NSE/BSE market data from the Upstox API**. No real money and no real orders are
ever involved — the platform's job is everything *around* the market feed:

- accounts & JWT auth
- a virtual funds wallet with an immutable ledger
- the full order lifecycle (place / modify / cancel), including MARKET / LIMIT / SL / SL-M
- a tick-driven **execution simulator** that fills orders against live ticks
- positions, holdings, T+1 settlement, MIS auto square-off
- equity, index F&O (with an option chain), currency & commodity futures
- realistic statutory charges (brokerage, STT, exchange txn, SEBI, stamp, GST) and P&L reports
- a leaderboard, per-user account reset, and a theming/settings screen

> **Design:** the UI was designed on a canvas first — see
> [`docs/DESIGN.md`](docs/DESIGN.md) and [`design/`](design/).

---

## Screens

A slim top nav + a **permanent watchlist rail** on the left (list tabs, search,
inline Buy/Sell/chart/remove) that doubles as the app's live-price engine.

`Dashboard` · `Chart` (candles, live last bar, IST axis) · `Orders` (order &
trade book) · `Positions` · `Holdings` · `Option chain` · `Reports` ·
`Leaderboard` · `Settings` (light/dark/system theme, accent colour, P&L colour
style) · `Login` / `Register`.

---

## How it works

Four small processes share one codebase and talk over Redis:

| Process | Module | Responsibility |
|---|---|---|
| **api** | `app.main:app` | REST + WebSocket for the browser (FastAPI / uvicorn) |
| **marketdata** | `app.workers.marketdata_main` | polls the provider for every watchlisted instrument + open position, writes the latest quote to Redis (`quote:<key>`, 180 s TTL) and publishes each tick to the `ticks` channel |
| **engine** | `app.services.execution.worker` | subscribes to `ticks`, matches resting orders, books fills through `portfolio_service`, settles the wallet, pushes order/position updates back over Redis |
| **scheduler** | `app.workers.scheduler_main` | 08:00 instrument-master sync, 15:15 MIS square-off, 15:45 EOD (square-off sweep + futures MTM + F&O expiry settlement + T+1) |

```
                    ┌──────────────┐   REST poll
   Upstox API ──────▶  marketdata  │◀─────────────  every watchlisted / held instrument
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
                        │    scheduler     │  daily jobs
                        └──────────────────┘
```

**Live prices** reach the browser two ways: the `/ws` WebSocket streams tick by
tick, and every price-bearing page also polls `/api/instruments/quote` every 4 s
as a fallback. Only **watchlisted instruments + your open positions** are ever
fetched — nothing else.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite, TypeScript, TanStack Query, Zustand, Tailwind CSS, lightweight-charts, date-fns-tz |
| Backend | FastAPI (async), SQLAlchemy 2.x (async), Alembic, APScheduler |
| Auth | JWT access/refresh (`python-jose`), `bcrypt` (SHA-256 pre-hash) |
| Data stores | PostgreSQL (system of record), Redis (live ticks, pub/sub, cache) |
| Market data | pluggable `MarketDataProvider` — `mock` (random-walk, no account) or `upstox` (REST quote polling + historical candles + option chain) |

---

## Project structure

```
.
├─ docker-compose.yml          # postgres, redis, api, marketdata, engine, scheduler, frontend
├─ .env.example                # copy to .env  (backend + compose config)
├─ docs/DESIGN.md              # design document
├─ design/                     # the design canvas sources (.dc.html + canvas.json + logo)
│
├─ backend/
│  ├─ pyproject.toml
│  ├─ Dockerfile
│  ├─ alembic/                 # 0001 baseline (create_all) + 0002 instruments.category
│  ├─ scripts/upstox_check.py  # standalone Upstox token / connectivity diagnostic
│  └─ app/
│     ├─ main.py               # app factory, CORS, health, dev schema-sync, theme-agnostic
│     ├─ config.py db.py redis_client.py
│     ├─ models/               # user, wallet, ledger, instrument, order, trade, position, holding, watchlist
│     ├─ core/                 # security, deps, exceptions, calendar (NSE/BSE/MCX hours + holidays)
│     ├─ api/                  # auth, instruments, watchlists, orders, portfolio, reports,
│     │                        # leaderboard, account, debug, ws
│     └─ services/
│        ├─ market_data/       # MarketDataProvider ABC + mock + upstox + classify + registry
│        ├─ execution/         # fills (decision) + engine (matching) + worker
│        ├─ pricing/           # charges.py (statutory + brokerage) + margin.py
│        ├─ order_service.py portfolio_service.py settlement.py
│        ├─ instrument_service.py market_service.py watchlist_service.py
│        └─ leaderboard_service.py
│
└─ frontend/
   ├─ Dockerfile / nginx.conf
   └─ src/
      ├─ api/                  # axios client (+ refresh interceptor), typed hooks, ws client
      ├─ store/                # auth, quotes, orderPad, chartFocus, theme  (all persisted where useful)
      ├─ lib/                  # format (INR / %), time (IST via date-fns-tz)
      ├─ components/           # Layout, WatchlistRail, OrderPad, InstrumentSearch, LivePrice, ErrorBoundary
      └─ pages/                # Dashboard, Chart, Orders, Positions, Holdings, OptionChain,
                               # Reports, Leaderboard, Settings, Login, Register
```

---

## Prerequisites

**Docker + Docker Compose** is enough. To run pieces locally you also need
Python 3.11+ (3.13 tested) and Node 20+ (22 tested), with Postgres and Redis
reachable.

---

## Environment files

Secrets and machine config live in `.env` files, which are **git-ignored**. The
repo ships `.env.example` templates.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Then set at least `SECRET_KEY` in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Key variables

| Variable | Default | Meaning |
|---|---|---|
| `ENV` | `dev` | in `dev` the API keeps the schema in sync on startup (no migration step) |
| `SECRET_KEY` | — | JWT signing key — **change it** |
| `DATABASE_URL` | `postgresql+asyncpg://paper:paper@localhost:5432/paper_trading` | async Postgres URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `OPENING_BALANCE` | `1000000` | virtual cash each new user starts with (₹) |
| `MARKET_DATA_PROVIDER` | `mock` | `mock` or `upstox` |
| `UPSTOX_API_KEY` / `_SECRET` / `_REDIRECT_URI` / `_ACCESS_TOKEN` | — | only for `MARKET_DATA_PROVIDER=upstox` |
| `MIS_EQUITY_LEVERAGE` / `FUT_MARGIN_PCT` / `OPTION_SELL_MARGIN_PCT` | `5` / `0.20` / `0.15` | paper margin model |
| `ENFORCE_MARKET_HOURS` | `false` | reject orders outside the segment's trading hours |
| `VITE_API_BASE_URL` | `http://localhost:8000` | where the frontend calls the API |

---

## Running it

```bash
cp .env.example .env            # set SECRET_KEY
docker compose up --build
```

- API — http://localhost:8000  (`/docs`, `/health`, `/api/debug/feed`)
- Frontend — http://localhost:5173

Open the frontend, register an account (you get ₹10,00,000 and a default
**"Popular"** watchlist of ~20 large-caps + indices), and start trading.

### Local dev without Docker for the backend

```bash
docker compose up postgres redis      # infra only
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# in other terminals, if you want them:
python -m app.workers.marketdata_main
python -m app.services.execution.worker
python -m app.workers.scheduler_main

cd ../frontend && cp .env.example .env && npm install && npm run dev
```

`ENV=dev` creates/repairs tables on API startup. For a real schema:
`cd backend && alembic upgrade head`.

---

## Using real Upstox data

Default is `mock` — a random-walk feed over ~8 NSE symbols + synthetic
NIFTY/BANKNIFTY option chains + GOLDM/SILVERM/USDINR futures — so the whole app
runs with **no broker account**.

To use **Upstox** (real NSE/BSE data), you need an Upstox account with API access:

1. Create an app at **https://account.upstox.com/developer/apps** with redirect
   URL `http://localhost:8000/api/instruments/upstox/callback`. Copy the API key + secret.
2. In `.env`: `MARKET_DATA_PROVIDER=upstox`, `UPSTOX_API_KEY=…`, `UPSTOX_API_SECRET=…`.
3. Generate a **daily access token** (Upstox tokens expire ~03:30 IST, no refresh token):
   - open `https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=<API_KEY>&redirect_uri=http://localhost:8000/api/instruments/upstox/callback`
   - log in, authorise, copy the `code` from the redirected URL
   - `POST https://api.upstox.com/v2/login/authorization/token` with
     `code`, `client_id`, `client_secret`, `redirect_uri`, `grant_type=authorization_code`
   - put the returned `access_token` in `.env` as `UPSTOX_ACCESS_TOKEN`
4. `docker compose up -d --force-recreate marketdata api scheduler`

There is **no auto-refresh** — when the token expires the `marketdata` process
logs a clear message and exits; regenerate the token and restart.
`backend/scripts/upstox_check.py` decodes your token and hits a few endpoints to
tell you exactly what's wrong.

---

## API overview

Interactive docs at `http://localhost:8000/docs`. Errors are
`{ "error": { "code": "...", "message": "..." } }`.

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/auth/register` · `/login` · `/refresh`, `GET /me` | register also creates the wallet + default watchlist |
| `GET` | `/api/instruments/search?q=&segment=&category=` | ranked search; `category` = EQUITY / ETF / INDEX / FUTURE / OPTION / MUTUAL_FUND / BOND / REIT_INVIT / COMMODITY / CURRENCY / SME / IPO |
| `GET` | `/api/instruments/quote?keys=` · `/{key}/candles` · `/underlyings` · `/expiries` · `/option-chain` | market data |
| `POST` | `/api/instruments/sync` | pull the provider instrument master into the DB |
| `GET/POST` | `/api/watchlists` (+ `/{id}/items`, `/{id}/order`, `/seed-popular`) | watchlist CRUD with quotes attached |
| `POST/GET` | `/api/orders` (+ `PUT`/`DELETE /{id}`), `GET /api/orders/trades/book` | place / modify / cancel / list; trade book |
| `GET` | `/api/portfolio/funds` · `/ledger` · `/positions` · `/holdings` · `/summary` | portfolio |
| `POST` | `/api/portfolio/square-off` · `/api/account/reset` | flatten MIS / full reset |
| `GET` | `/api/reports/pnl` · `/reports/charges` · `/api/leaderboard` | analytics |
| `GET` | `/api/debug/feed` | **no auth** — one-call health check for the whole live-data pipeline |
| `WS` | `/ws?token=` | live ticks + order/position push |

---

## Tests

```bash
cd backend
pip install -e ".[dev]"
pytest                # 82 tests, throwaway SQLite, no Postgres/Redis needed
```

Covers auth, wallet/ledger, the charge & margin models, position math, the fill
rules (MARKET/LIMIT/SL latch), the order→engine→portfolio path, MIS square-off,
T+1 settlement, F&O (futures margin, option premium, expiry cash-settlement),
instrument classification & search, the default-watchlist seed, the leaderboard,
and commodity/currency futures.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` on 5432/6379 | infra not up — `docker compose up postgres redis` |
| API 500s about missing columns | set `ENV=dev` (auto-repair) or `alembic upgrade head` |
| `marketdata` crash-loops | `MARKET_DATA_PROVIDER=upstox` with a missing/expired token — set `mock` or regenerate (`backend/scripts/upstox_check.py`) |
| Prices frozen / % shows 0 | open `http://localhost:8000/api/debug/feed` — `channel_ticks_500ms > 0` means the feed is live; a large `age_seconds` means the feed stopped or the token expired |
| Watchlist empty after first run | click **Load popular list**, or `POST /api/watchlists/seed-popular` (needs the instrument master synced) |
| Frontend blank | rebuild (`docker compose up -d --build frontend`) + hard refresh; check the browser console |
| Chart daily bar off by a day | rebuild the frontend — bars are keyed by IST calendar date |

---

## Deploying

`docker compose up --build` also builds a **`frontend`** container (nginx serving
the built SPA) on `:5173`. Set `VITE_API_BASE_URL` to the public API URL before
building. Run `alembic upgrade head` for a real schema instead of the `ENV=dev`
auto-repair. Set `ENFORCE_MARKET_HOURS=true` in production.

---

## Status — all planned phases complete

| Phase | Scope |
|---|---|
| **0** | scaffold, Docker services, config, health, Alembic |
| **1** | accounts, JWT/refresh, virtual wallet, ledger, account reset |
| **2** | pluggable market-data provider, instrument master + classification, watchlists, live quotes over WebSocket, charts |
| **3** | order lifecycle + margin block, tick-driven execution engine, statutory charge model, positions & holdings |
| **4** | market calendar, MIS auto square-off, T+1 settlement, daily futures MTM, P&L + charges reports |
| **5** | F&O — lots, margin, option chain, expiry cash-settlement |
| **6** | currency & commodity segments, leaderboard, `frontend` container |
| **+** | full UI redesign, permanent watchlist rail, paper-boat logo, light/dark themes + accent picker, IST-correct charts, live-data resilience (quote TTL, WS token refresh, REST fallback), `/api/debug/feed` |
