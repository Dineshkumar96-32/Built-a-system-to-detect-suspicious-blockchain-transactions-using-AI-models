"""
app/routes/transactions.py
───────────────────────────
Transaction endpoints: paginated list, single fetch, SSE stream.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Transaction
from app.schemas.transactions import TransactionOut, TransactionPage
from auth.auth import TokenData, get_current_user  # type: ignore[import]

router = APIRouter(prefix="/transactions", tags=["Transactions"])

_MAX_PAGE_SIZE = 200


# ── Helpers (mockable in tests) ───────────────────────────────

async def get_transactions(
    db: AsyncSession,
    page: int,
    size: int,
    chain: str | None,
    min_score: float | None,
    wallet: str | None,
    flagged: bool | None,
) -> TransactionPage:
    filters = []
    if chain:
        filters.append(Transaction.chain == chain)
    if min_score is not None:
        filters.append(Transaction.anomaly_score >= min_score)
    if wallet:
        filters.append(
            (Transaction.from_address == wallet) | (Transaction.to_address == wallet)
        )
    if flagged is not None:
        filters.append(Transaction.flagged == flagged)

    q = select(Transaction).order_by(desc(Transaction.created_at))
    if filters:
        q = q.where(and_(*filters))

    total_q = select(Transaction).where(and_(*filters)) if filters else select(Transaction)
    total = len((await db.execute(total_q)).scalars().all())

    q = q.offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()

    return TransactionPage(
        total=total,
        page=page,
        size=size,
        items=[TransactionOut.model_validate(r) for r in rows],
    )


async def get_transaction_by_hash(
    db: AsyncSession, tx_hash: str
) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(Transaction.tx_hash == tx_hash)
    )
    return result.scalar_one_or_none()


# ── Routes ────────────────────────────────────────────────────

@router.get("", response_model=TransactionPage)
async def list_transactions(
    page:      int   = Query(1,    ge=1),
    size:      int   = Query(50,   ge=1, le=_MAX_PAGE_SIZE),
    chain:     str | None  = Query(None),
    min_score: float | None = Query(None, ge=0.0, le=1.0),
    wallet:    str | None  = Query(None),
    flagged:   bool | None = Query(None),
    db:        AsyncSession = Depends(get_db),
    _:         TokenData    = Depends(get_current_user),
) -> TransactionPage:
    return await get_transactions(db, page, size, chain, min_score, wallet, flagged)


@router.get("/stream")
async def stream_transactions(
    request: Request,
    _: TokenData = Depends(get_current_user),
) -> StreamingResponse:
    """Server-Sent Events stream of live transactions."""

    async def event_gen() -> AsyncGenerator[str, None]:
        broker = request.app.state.broker
        async for msg in broker.subscribe("transactions"):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(msg.payload)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/search", response_model=list[TransactionOut])
async def search_transactions(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    _: TokenData = Depends(get_current_user),
) -> list[TransactionOut]:
    """Search transactions by hash, from_address, or to_address."""
    from sqlalchemy import or_
    stmt = select(Transaction).where(
        or_(
            Transaction.tx_hash.ilike(f"%{q}%"),
            Transaction.from_address.ilike(f"%{q}%"),
            Transaction.to_address.ilike(f"%{q}%")
        )
    ).limit(50)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [TransactionOut.model_validate(r) for r in rows]


@router.get("/{tx_hash}", response_model=TransactionOut)
async def get_transaction(
    tx_hash: str,
    db: AsyncSession = Depends(get_db),
    _:  TokenData    = Depends(get_current_user),
) -> TransactionOut:
    tx = await get_transaction_by_hash(db, tx_hash)
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TransactionOut.model_validate(tx)
