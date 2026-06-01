"""
app/routes/rules.py
────────────────────
Alert rule CRUD: GET/POST/PUT/DELETE/toggle.
Admin scope required for DELETE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import AlertRule
from auth.auth import Role, TokenData, get_current_user, require_role  # type: ignore[import]

router = APIRouter(prefix="/rules", tags=["Alert Rules"])


class RuleBody(BaseModel):
    name:        str
    description: str = ""
    severity:    str = "HIGH"
    rule_json:   dict = {}
    active:      bool = True


async def list_rules(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.execute(select(AlertRule))).scalars().all()
    return [_d(r) for r in rows]


async def create_rule(db: AsyncSession, body: RuleBody, created_by: str) -> dict[str, Any]:
    rule = AlertRule(
        name=body.name, description=body.description or None,
        severity=body.severity, rule_json=body.rule_json,
        active=body.active, created_by=created_by,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _d(rule)


async def update_rule(db: AsyncSession, rule_id: str, body: RuleBody) -> dict[str, Any]:
    rule = await _get(db, rule_id)
    rule.name = body.name; rule.description = body.description or None
    rule.severity = body.severity; rule.rule_json = body.rule_json
    rule.active = body.active; rule.updated_at = datetime.now(timezone.utc)
    await db.commit(); await db.refresh(rule)
    return _d(rule)


async def delete_rule(db: AsyncSession, rule_id: str) -> bool:
    rule = await _get(db, rule_id)
    await db.delete(rule); await db.commit()
    return True


async def toggle_rule(db: AsyncSession, rule_id: str) -> dict[str, Any]:
    rule = await _get(db, rule_id)
    rule.active = not rule.active
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit(); await db.refresh(rule)
    return _d(rule)


async def _get(db: AsyncSession, rule_id: str) -> AlertRule:
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id!r} not found")
    return rule


def _d(r: AlertRule) -> dict[str, Any]:
    return {
        "id": r.id, "name": r.name, "description": r.description,
        "severity": r.severity, "rule_json": r.rule_json, "active": r.active,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("")
async def get_rules(db: AsyncSession = Depends(get_db), _: TokenData = Depends(get_current_user)) -> list[dict[str, Any]]:
    return await list_rules(db)


@router.post("")
async def post_rule(body: RuleBody, db: AsyncSession = Depends(get_db), current: TokenData = Depends(get_current_user)) -> dict[str, Any]:
    return await create_rule(db, body, current.sub)


@router.put("/{rule_id}")
async def put_rule(rule_id: str, body: RuleBody, db: AsyncSession = Depends(get_db), _: TokenData = Depends(get_current_user)) -> dict[str, Any]:
    return await update_rule(db, rule_id, body)


@router.delete("/{rule_id}")
async def del_rule(rule_id: str, db: AsyncSession = Depends(get_db), _: TokenData = Depends(require_role(Role.ADMIN)())) -> dict[str, Any]:
    await delete_rule(db, rule_id)
    return {"deleted": rule_id}


@router.post("/{rule_id}/toggle")
async def toggle(rule_id: str, db: AsyncSession = Depends(get_db), _: TokenData = Depends(get_current_user)) -> dict[str, Any]:
    return await toggle_rule(db, rule_id)
