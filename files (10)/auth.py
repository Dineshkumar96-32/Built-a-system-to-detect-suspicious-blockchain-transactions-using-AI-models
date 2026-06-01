"""app/schemas/auth.py"""
from __future__ import annotations
from typing import List
from pydantic import BaseModel

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800

class UserOut(BaseModel):
    sub: str
    role: str
    scopes: List[str] = []
