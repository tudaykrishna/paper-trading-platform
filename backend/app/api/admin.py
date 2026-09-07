"""User-facing account maintenance (reset). Not an operator console."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.wallet import FundsOut
from app.services import wallet_service

router = APIRouter(prefix="/api/account", tags=["account"])


@router.post("/reset", response_model=FundsOut)
async def reset_account(user: CurrentUser, db: DbSession) -> FundsOut:
    """Flatten all positions/holdings and restore the virtual wallet."""
    wallet = await wallet_service.reset_account(db, user.id)
    return FundsOut(
        cash_balance=wallet.cash_balance,
        blocked_margin=wallet.blocked_margin,
        available_cash=wallet.available_cash,
        opening_balance=wallet.opening_balance,
    )
