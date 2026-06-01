from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

class SettingsUpdate(BaseModel):
    webhook_enabled: bool | None = None
    webhook_url: str | None = None

@router.get("/")
async def get_current_settings() -> Dict[str, Any]:
    return {
        "webhook_enabled": settings.webhook_enabled,
        "webhook_url": settings.webhook_url
    }

@router.post("/")
async def update_settings(update: SettingsUpdate) -> Dict[str, Any]:
    try:
        if update.webhook_enabled != None:
            settings.webhook_enabled = update.webhook_enabled
        if update.webhook_url != None:
            settings.webhook_url = update.webhook_url
            
        return {
            "status": "success",
            "webhook_enabled": settings.webhook_enabled,
            "webhook_url": settings.webhook_url
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
