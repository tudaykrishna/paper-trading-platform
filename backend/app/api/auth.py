"""Registration, login, token refresh, current-user."""
from __future__ import annotations

from fastapi import APIRouter, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import AuthError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import wallet_service, watchlist_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> TokenPair:
    exists = (
        await db.execute(select(User.id).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if exists:
        raise ValidationError("email already registered", code="email_taken")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # race on unique email
        raise ValidationError("email already registered", code="email_taken") from exc

    await wallet_service.create_wallet(db, user.id)
    await watchlist_service.create_default(db, user.id)
    return _tokens(user.id)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthError("incorrect email or password")
    if not user.is_active:
        raise AuthError("account disabled")
    return _tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        user_id = decode_token(payload.refresh_token, "refresh")
    except JWTError as exc:
        raise AuthError("invalid refresh token") from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("user not found or inactive")
    return _tokens(user_id)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
