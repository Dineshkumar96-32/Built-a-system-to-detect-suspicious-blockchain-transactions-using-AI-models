"""
BlockShield — Auth API routes
POST /api/v1/auth/token       — issue JWT (password flow)
POST /api/v1/auth/refresh     — refresh JWT
POST /api/v1/auth/keys        — create API key
GET  /api/v1/auth/keys        — list API keys
DELETE /api/v1/auth/keys/{id} — revoke API key
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_current_user,
    require_scope,
    verify_password,
    hash_password,
)
from app.core.config import settings
from app.db.models import ApiKey
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str] = ["read"]
    expires_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_key: str  # Only returned ONCE at creation time


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password flow.
    In production, validate against your user table.
    Currently validates against APP_SECRET_KEY as a demo master password.
    Replace with real user lookup + hash_password verify.
    """
    # TODO: replace with real user DB lookup
    if form.username != "admin" or not verify_password(
        form.password, hash_password(settings.APP_SECRET_KEY)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    return TokenResponse(
        access_token=create_access_token(subject=form.username, scopes=["admin"]),
        refresh_token=create_refresh_token(subject=form.username),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Not a refresh token.")
    return TokenResponse(
        access_token=create_access_token(subject=payload["sub"], scopes=["admin"]),
        refresh_token=create_refresh_token(subject=payload["sub"]),
    )


@router.post("/keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_scope("admin")),
):
    raw_key, key_hash, prefix = generate_api_key()
    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    key = ApiKey(
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
        scopes=body.scopes,
        expires_at=expires_at,
        created_by=user.subject,
    )
    db.add(key)
    await db.flush()

    resp = ApiKeyCreatedResponse.model_validate(key)
    resp.raw_key = raw_key  # shown ONCE
    return resp


@router.get("/keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_scope("admin")),
):
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return result.scalars().all()


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_scope("admin")),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found.")
    key.is_active = False
