"""Public-ish leaderboard (auth still required)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.services import leaderboard_service

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(user: CurrentUser, db: DbSession, limit: int = Query(50, le=200)) -> dict:
    rows = await leaderboard_service.compute(db, limit=limit)
    me = next((r for r in rows if r["user_id"] == user.id), None)
    return {"rows": rows, "me": me}
