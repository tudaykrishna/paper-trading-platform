"""FastAPI dependencies: current user resolution."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import decode_token
from app.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    try:
        user_id = decode_token(token, "access")
    except JWTError as exc:  # noqa: BLE001
        raise AuthError("invalid or expired token") from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("user not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
