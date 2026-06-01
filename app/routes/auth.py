"""
app/routes/auth.py
───────────────────
Auth endpoints: login, token refresh, current user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User
from app.schemas.auth import TokenPair, UserOut, RefreshRequest
from auth.auth import (  # type: ignore[import]
    Role,
    TokenData,
    create_token_pair,
    decode_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/token", response_model=TokenPair)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    result = await db.execute(select(User).where(User.email == form.username))
    user: User | None = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return create_token_pair(sub=user.email, role=Role(user.role))


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest) -> TokenPair:
    data = decode_token(body.refresh_token)
    return create_token_pair(sub=data.sub, role=data.role)


@router.get("/me", response_model=UserOut)
async def me(current: TokenData = Depends(get_current_user)) -> UserOut:
    return UserOut(sub=current.sub, role=current.role, scopes=current.scopes)
