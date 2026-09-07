"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    admin,
    auth,
    debug,
    instruments,
    leaderboard,
    orders,
    portfolio,
    reports,
    watchlists,
    ws,
)
from sqlalchemy import inspect, text

from app.config import settings
from app.core.exceptions import AppError
from app.db import Base, engine
from app.redis_client import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


def _dev_schema_sync(sync_conn) -> None:
    """Create missing tables. ``instruments`` (no inbound FKs, repopulated by the
    scheduler sync) is dropped + recreated whenever its ``category`` column is
    absent or not a plain string, so schema changes to it need no migration in dev.
    """
    import app.models  # noqa: F401  (register metadata)

    insp = inspect(sync_conn)
    tables = insp.get_table_names()
    if "instruments" in tables:
        cat = next((c for c in insp.get_columns("instruments") if c["name"] == "category"), None)
        cat_type = str(cat["type"]).upper() if cat else ""
        if cat is None or not any(t in cat_type for t in ("VARCHAR", "CHAR", "TEXT", "STRING")):
            logger.warning("dev: rebuilding instruments table (category col = %r)", cat_type or None)
            app.models.Instrument.__table__.drop(sync_conn)
            if sync_conn.dialect.name == "postgresql":
                sync_conn.execute(text("DROP TYPE IF EXISTS asset_category"))

    for table in Base.metadata.sorted_tables:
        if table.name in tables and table.name != "instruments":
            existing = {c["name"] for c in insp.get_columns(table.name)}
            missing = {c.name for c in table.columns} - existing
            if missing:
                logger.warning(
                    "dev: table %s missing columns %s — run `alembic upgrade head`",
                    table.name, missing,
                )
    Base.metadata.create_all(sync_conn)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience: keep the schema in sync without a migration step.
    # In prod (ENV != dev) rely on `alembic upgrade head`.
    if settings.env == "dev":
        async with engine.begin() as conn:
            await conn.run_sync(_dev_schema_sync)
        logger.info("dev mode: schema ensured")
    yield
    await redis_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Paper Trading API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        redis_ok = "ok"
        try:
            await redis_client.ping()
        except Exception:  # noqa: BLE001
            redis_ok = "down"
        return {"status": "ok", "redis": redis_ok, "env": settings.env}

    app.include_router(auth.router)
    app.include_router(portfolio.router)
    app.include_router(admin.router)
    app.include_router(instruments.router)
    app.include_router(watchlists.router)
    app.include_router(orders.router)
    app.include_router(reports.router)
    app.include_router(leaderboard.router)
    app.include_router(debug.router)
    app.include_router(ws.router)
    return app


app = create_app()
