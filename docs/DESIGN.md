# Paper Trading Platform — Design Document

> **Status: fully implemented.** This is the original phased plan the project was
> built against — every phase is complete. Current state and setup are in the
> [README](../README.md); the UI was designed on a canvas (see [`design/`](../design/)).
> A few things evolved during the build: the standalone Watchlist page became a
> permanent left rail, market data uses REST quote polling (not the protobuf
> WebSocket), the Upstox token is supplied manually with no auto-refresh, and the
> UI gained a light/dark theme with a user-configurable accent colour.

## Context

Build a **paper (virtual) trading platform**. Real money is never
involved: users get a virtual cash wallet and place simulated orders that are
"filled" against **live NSE/BSE market data pulled from a broker API**. The
platform's real responsibility is everything *around* the market feed — user
accounts, virtual funds, order lifecycle, an execution/matching simulator,
positions/holdings, realistic charges, and P&L reporting.

Decisions locked in from planning:

| Area | Choice |
|------|--------|
| Stack | React (Vite) frontend + FastAPI (Python) backend |
| Datastores | PostgreSQL (system of record) + Redis (live ticks, pub/sub, cache) |
| Market data | Broker API — **Upstox API v2** as the first adapter (free developer account, WebSocket ticks + historical candles), behind a pluggable `MarketDataProvider` interface so Kite/Dhan can be added later |
| Instruments | "Everything" — Equity cash, Equity/Index F&O, Currency F&O, Commodity (MCX) — delivered in phases |
| Scale | Personal / portfolio project — single small deployment, tens of users, minimal infra |

Because "everything" is a large surface but the audience is small, the build is
**phased**: a fully working equity product first, then derivatives layered on the
same engine.

---

## Architecture Overview

```
                    ┌─────────────────┐
   Upstox WS/REST ──▶ Market Data Svc  │──┐  (ticks)
                    └─────────────────┘  │
                                         ▼
   ┌────────┐   REST/WS   ┌──────────┐  Redis pub/sub  ┌───────────────────┐
   │ React  │ ◀─────────▶ │ FastAPI  │ ◀─────────────▶ │ Execution Engine  │
   │  SPA   │             │  API     │                 │ (background worker)│
   └────────┘             └────┬─────┘                 └─────────┬─────────┘
                               │                                 │
                               ▼                                 ▼
                        ┌────────────┐                    writes fills / positions
                        │ PostgreSQL │ ◀──────────────────────────┘
                        └────────────┘
                               ▲
                        ┌──────┴───────┐
                        │  Scheduler   │  EOD square-off, MTM, instrument sync,
                        │ (APScheduler)│  holiday calendar, account resets
                        └──────────────┘
```

**Processes (all runnable on one machine via `docker-compose` or a Procfile):**

1. `api` — FastAPI (uvicorn), REST + WebSocket for the frontend.
2. `marketdata` — connects to Upstox WebSocket, normalizes ticks, writes latest
   quote to Redis (`quote:<instrument_key>`) and publishes to `ticks` channel.
3. `engine` — subscribes to `ticks`, evaluates resting/pending orders, produces
   fills, updates positions/holdings and wallet, pushes order/position updates to
   a Redis channel the `api` relays over WebSocket.
4. `scheduler` — APScheduler jobs (see Scheduler section).

Keep 2/3/4 as separate entrypoints but in the **same codebase** sharing models.

---

## Repository Layout

```
Paper_trading/
├─ docker-compose.yml            # postgres, redis, api, marketdata, engine, scheduler
├─ .env.example
├─ backend/
│  ├─ pyproject.toml             # fastapi, uvicorn, sqlalchemy, alembic, pydantic-settings,
│  │                             # asyncpg, redis, httpx, websockets, apscheduler, bcrypt,
│  │                             # python-jose
│  ├─ alembic/                   # migrations
│  ├─ app/
│  │  ├─ main.py                 # FastAPI app factory, routers, WS endpoint
│  │  ├─ config.py               # pydantic Settings (env)
│  │  ├─ db.py                   # async engine + session
│  │  ├─ redis_client.py
│  │  ├─ models/                 # SQLAlchemy: user, wallet, instrument, order, trade,
│  │  │                          # position, holding, watchlist, ledger, corporate_action
│  │  ├─ schemas/                # Pydantic request/response
│  │  ├─ api/
│  │  │  ├─ auth.py              # register, login, refresh, me
│  │  │  ├─ instruments.py       # search, quote, historical candles, option chain
│  │  │  ├─ watchlists.py
│  │  │  ├─ orders.py            # place, modify, cancel, list, order book
│  │  │  ├─ portfolio.py         # positions, holdings, funds, P&L, trade book
│  │  │  └─ admin.py             # reset account, seed
│  │  ├─ services/
│  │  │  ├─ market_data/
│  │  │  │  ├─ base.py           # MarketDataProvider ABC (subscribe, get_quote,
│  │  │  │  │                    # get_candles, instrument_master, auth)
│  │  │  │  ├─ upstox.py         # Upstox v2 adapter (OAuth, WS v3, REST)
│  │  │  │  ├─ mock.py           # random-walk provider (no account needed)
│  │  │  │  └─ registry.py       # provider selection from config
│  │  │  ├─ execution/
│  │  │  │  ├─ engine.py         # tick loop, order matching rules
│  │  │  │  ├─ fills.py          # fill price logic per order type
│  │  │  │  └─ worker.py         # entrypoint
│  │  │  ├─ pricing/
│  │  │  │  ├─ charges.py        # brokerage, STT, txn, GST, stamp, SEBI per segment
│  │  │  │  └─ margin.py         # required margin per product/segment
│  │  │  ├─ portfolio_service.py # position/holding netting, avg price, realized/unrealized
│  │  │  ├─ wallet_service.py    # debit/credit + immutable ledger rows
│  │  │  └─ settlement.py        # intraday square-off, F&O expiry settlement, MTM
│  │  ├─ workers/
│  │  │  ├─ marketdata_main.py
│  │  │  └─ scheduler_main.py
│  │  └─ core/                   # security (JWT, hashing), deps, exceptions, calendar
│  └─ tests/                     # pytest — engine rules, charges, margin, portfolio math
└─ frontend/
   ├─ package.json               # react, vite, react-router, @tanstack/react-query,
   │                             # zustand, axios, lightweight-charts, tailwind
   └─ src/
      ├─ api/                    # axios client, react-query hooks
      ├─ store/                  # auth + live-quote stores, WS client
      ├─ pages/                  # Login, Dashboard, Watchlist, Chart, Orders,
      │                          # Positions, Holdings, Funds, Reports, OptionChain
      └─ components/             # OrderPad, QuoteTicker, DepthLadder, PnLCard, InstrumentSearch
```

---

## Data Model (PostgreSQL, key tables)

- **users** — id, email, password_hash, name, created_at, is_active.
- **wallets** — user_id (1:1), cash_balance, blocked_margin, opening_balance.
- **ledger_entries** — append-only: wallet_id, ts, type (DEPOSIT/RESET/FILL/CHARGE/MTM/SETTLEMENT), amount, balance_after, ref_order_id, note.
- **instruments** — instrument_key (broker), exchange, segment (EQ/FO/CDS/MCX), tradingsymbol, name, isin, lot_size, tick_size, expiry, strike, option_type, underlying_key, freeze_qty. Synced daily from broker instrument master.
- **watchlists** / **watchlist_items** — user watchlists (default one created on signup).
- **orders** — user_id, instrument_key, side (BUY/SELL), qty, product (CNC/MIS/NRML), order_type (MARKET/LIMIT/SL/SL-M), price, trigger_price, status (PENDING/OPEN/COMPLETE/REJECTED/CANCELLED), filled_qty, avg_fill_price, validity (DAY/IOC), placed_at, updated_at, parent_order_id (for bracket/cover — later).
- **trades** — order_id, instrument_key, side, qty, price, ts, charges_breakdown (JSONB), net_amount.
- **positions** — user_id, instrument_key, product, net_qty, avg_price, realized_pnl, day (for intraday); recomputed from trades, keyed per trading day for MIS.
- **holdings** — user_id, instrument_key, qty, avg_price, settled_qty (T+1), last_price cache.
- **corporate_actions** — instrument_key, type (SPLIT/BONUS/DIV), ratio, ex_date (Phase 6, optional).

Positions/holdings are **derived** — always rebuildable by replaying `trades`.
This makes the engine safe to restart.

---

## Execution / Matching Simulator (the core)

Runs in the `engine` process. On each tick for a subscribed instrument:

1. Load OPEN orders for that instrument from a Redis-backed index (hydrated from DB on start).
2. Apply fill rules (`services/execution/fills.py`):
   - **MARKET** — fill immediately at LTP (optionally cross the spread: BUY at ask, SELL at bid when depth available). Slippage config: `SLIPPAGE_BPS` default 0.
   - **LIMIT** — fill when `LTP <= price` (BUY) or `LTP >= price` (SELL); fill at limit price (or better = LTP if it improves).
   - **SL / SL-M** — when `LTP` crosses `trigger_price`, convert to LIMIT/MARKET and evaluate same tick.
   - Partial fills optional (default: all-or-nothing against LTP; enable qty-vs-traded-volume cap later).
3. On fill: write `trades` row with charges (`pricing/charges.py`), update wallet via `wallet_service` (release blocked margin, debit/credit cash + charges, write ledger), recompute `positions`/`holdings` via `portfolio_service`, set order COMPLETE.
4. Publish `order_update` + `position_update` to Redis → `api` relays to that user's WebSocket.

**Order placement path** (`api/orders.py` → validation):
- Validate instrument tradable now (segment market hours + holiday calendar in `core/calendar.py`).
- Compute required margin (`pricing/margin.py`); reject if `cash - blocked < required`.
- Block margin, persist order OPEN, push to engine's Redis index. MARKET/marketable orders are picked up on the next tick (near-instant during market hours).

**Fill price when market closed / no ticks:** orders rest as OPEN; on next session open the engine processes them against the first tick (or reject AMO-style — configurable).

---

## Segment-specific logic ("Everything")

Built on the same order/trade/position core; differences isolated in `pricing/` and `settlement.py`:

- **Equity cash (EQ)** — CNC (delivery → `holdings`, T+1 `settled_qty`), MIS (intraday → auto square-off 15:15). Charges: brokerage (₹0 delivery / ₹20 or 0.05% intraday), STT, exchange txn, GST, SEBI, stamp duty.
- **Equity/Index F&O (FO)** — qty in lots × `lot_size`; product NRML/MIS; margin = SPAN+exposure approximation (start with exchange-published margin % per instrument, or fixed 15–20% for futures, full premium for long options, span-style for short options). MTM daily on futures. **Expiry settlement** (`settlement.py`): index/stock options → cash-settle at intrinsic vs settlement price, then position closed; futures → settle at final settlement price. No physical delivery.
- **Currency F&O (CDS)** — same as FO with CDS lot sizes; market hours 09:00–17:00.
- **Commodity (MCX)** — futures/options; trading hours to 23:30 (23:55 in some seasons); separate holiday list. Margin % higher.

Market hours + holidays: `core/calendar.py` holds per-segment session windows and a
static NSE/BSE/MCX holiday list for the year, refreshed manually.

---

## Scheduler jobs (APScheduler, `scheduler_main.py`)

| Time (IST) | Job |
|-----------|-----|
| 08:00 daily | Sync broker **instrument master** into `instruments` |
| 09:00 / segment open | Mark session open; hydrate engine order index |
| 15:15 | Auto **square-off MIS** equity positions (place counter MARKET orders) |
| 15:30 / segment close | Mark session close; snapshot day P&L |
| 15:45 | **EOD MTM** on F&O futures; move filled CNC buys toward T+1 settlement |
| On expiry day post-close | **F&O expiry settlement** for expiring contracts |
| Configurable | **Account reset** — restore virtual wallet to opening balance, flatten positions (per-user endpoint + optional weekly cron) |

---

## Market Data Provider abstraction

`services/market_data/base.py` defines:

```python
class MarketDataProvider(ABC):
    async def authenticate(self) -> None: ...
    async def instrument_master(self) -> list[InstrumentDTO]: ...
    async def subscribe(self, instrument_keys: list[str]) -> None: ...
    def stream(self) -> AsyncIterator[TickDTO]: ...           # normalized ticks
    async def get_quote(self, keys: list[str]) -> dict[str, QuoteDTO]: ...
    async def get_candles(self, key, interval, frm, to) -> list[Candle]: ...
```

`mock.py` is a deterministic random-walk feed used by default so the platform runs
with no broker account.

`upstox.py` implements it against **Upstox API v2**: the instrument master asset
file, `GET /v2/market-quote/quotes` for quotes, `GET /v2/historical-candle/...`
for charts, and `GET /v2/option/chain` for the option-chain page. The live
`stream()` currently **polls** the quote endpoint on a short interval (no extra
deps, works outside market hours); swapping in the protobuf Market-Data-Feed
WebSocket only touches this file. Subscription list = union of all users'
watchlist + open positions/holdings, refreshed every 30s by the `marketdata`
worker.

> Note: Upstox (like all Indian brokers) issues a **daily** access token with no
> refresh token. The token is supplied manually via `UPSTOX_ACCESS_TOKEN` in
> `.env` (see README Step 3). There is **no auto-refresh** — when the token is
> stale the `marketdata` process logs a clear message and exits; regenerate the
> token and restart. `mock` stays the default provider for offline dev.

---

## Frontend (React + Vite)

- **Auth**: login/register, JWT access token in a persisted store + refresh token, `axios` interceptor.
- **Live quotes**: single app WebSocket (`/ws`) → zustand `quoteStore`; components subscribe by instrument_key. React Query for REST resources (orders, positions, funds).
- **Pages**: Dashboard (funds + day P&L + holdings summary), Watchlist (add/remove, live LTP/%chg, click → OrderPad), Chart (`lightweight-charts` + historical candles + interval switch), Orders (order book / trade book, modify/cancel), Positions (MIS/NRML, live MTM, square-off), Holdings (CNC, live value, P&L), Funds (balance, blocked margin, ledger), Option Chain (strikes, OI, LTP, click to trade), Reports (realized P&L, charges, per-day), Profile/Reset.
- **OrderPad** component: side, qty (lots for FO), product, order type, price/trigger, live margin-required preview, estimated charges.

---

## Build Phases

| Phase | Deliverable |
|-------|-------------|
| **0 — Scaffold** | Repo layout, `docker-compose` (pg+redis), FastAPI skeleton, React skeleton, Alembic, config, health checks |
| **1 — Accounts & funds** | Register/login/JWT, wallet with opening balance (e.g. ₹10,00,000), ledger, `/me`, reset endpoint |
| **2 — Market data** | Upstox adapter (auth + instrument master + WS), `marketdata` process, Redis quote cache, instrument search API, watchlists, live quotes over app WS, historical candles + Chart page |
| **3 — Equity trading** | Order place/modify/cancel + validation + margin block, `engine` process with MARKET/LIMIT/SL fills, trades, charges engine, positions/holdings, portfolio APIs, OrderPad + Orders/Positions/Holdings pages |
| **4 — EOD & reports** | Calendar/holidays, MIS auto square-off, T+1 holding settlement, EOD snapshots, realized P&L + charges reports page |
| **5 — F&O** | Lot handling, margin engine (futures % + option premium/short-margin), NRML product, option chain API + page, daily MTM, expiry settlement job |
| **6 — Currency & Commodity** | CDS + MCX segments, per-segment hours/holidays, margin %; leaderboard, corporate actions (optional), deploy notes |

MVP = Phases 0–4 (a complete equity paper-trading app). 5–6 extend it.

---

## Key reuse / library choices (no need to hand-roll)

- **Auth**: `bcrypt` (direct, with a SHA-256 pre-hash) + `python-jose` for JWT.
  *(passlib was dropped — it is broken on Python 3.13 / bcrypt 4.x.)*
- **DB**: SQLAlchemy 2.x async + Alembic; positions/holdings **derived from trades** (replayable) rather than a bespoke event store.
- **Scheduling**: APScheduler (single-node, fits "personal project").
- **Charts**: TradingView `lightweight-charts` (free) — do not build a charting lib.
- **Upstox**: official `upstox-python-sdk` if it covers WS v3 cleanly, else raw `httpx` + `websockets` (adapter isolates the choice).
- **Charges math**: implement once in `pricing/charges.py` from published SEBI/exchange rates; unit-test against a published broker brokerage-calculator's values.
- **Market calendar**: static per-year holiday list (NSE/BSE/MCX) — no reliable free API.

---

## Verification

**Per phase, automated (`pytest` in `backend/tests/`):**
- `test_auth.py` — register/login/refresh/protected-route.
- `test_wallet.py` — opening balance, margin block/release, fill settlement, reset.
- `test_charges.py` — brokerage/STT/GST/stamp for delivery vs intraday vs FO match a published broker brokerage calculator to the paisa.
- `test_margin.py` — required margin per product/segment; order rejected when wallet insufficient.
- `test_engine_fills.py` — feed synthetic tick sequences: MARKET fills at LTP; LIMIT fills only on cross; SL triggers then fills; no fill when price never crosses.
- `test_portfolio.py` — buy 100 @100 then 100 @110 ⇒ avg 105 qty 200; partial sell realizes correct P&L; short then cover.
- `test_settlement.py` — MIS square-off flattens day positions; option expiry cash-settles at intrinsic; CNC buy becomes settled at T+1.
- `test_calendar.py` — orders rejected outside segment hours / on holidays.

**End-to-end (manual, during market hours):**
1. `docker compose up`; run Alembic migrations; set `UPSTOX_ACCESS_TOKEN` in `.env` (README Step 3) and confirm the feed connects.
2. Register a user → wallet shows opening balance.
3. Add RELIANCE to watchlist → LTP ticks live in the UI; open Chart → candles load, interval switch works.
4. Place a **MARKET BUY** 10 qty CNC → order COMPLETE within a tick, cash debited + charges in ledger, holding appears with live P&L.
5. Place a **LIMIT SELL** above LTP → stays OPEN; drop the limit below LTP (modify) → fills; realized P&L correct.
6. Place a **MIS BUY**, leave open to 15:15 → auto square-off order appears, position flat.
7. Place an **SL-M** order, watch it trigger when LTP crosses.
8. (Phase 5) Buy 1 lot NIFTY future → margin blocked correctly; buy an option → full premium debited; option chain page shows live LTP/OI; hold a weekly option to expiry → cash-settled at intrinsic.
9. Hit **reset account** → positions flat, wallet back to opening balance, ledger shows RESET.
10. Restart `engine` process mid-session → open orders re-hydrate, positions unchanged (replay from trades).

**Load sanity (personal-project scale):** simulate ~50 users / ~200 instruments subscribed; confirm one `marketdata` connection + Redis pub/sub keeps engine tick-to-fill latency < ~500ms.
