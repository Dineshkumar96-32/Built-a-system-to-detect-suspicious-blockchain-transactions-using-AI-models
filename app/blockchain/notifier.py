"""
app/blockchain/notifier.py
Handles asynchronous webhook dispatching for alerts.
"""
import httpx
import asyncio
from typing import Dict, Any
from app.core.config import get_settings
from app.core.logger import get_logger

settings = get_settings()
logger = get_logger("blockshield.notifier")

async def dispatch_webhook(alert_data: Dict[str, Any]) -> None:
    if not settings.webhook_enabled or not settings.webhook_url:
        return
        
    # Format the payload for typical webhooks (e.g. Discord/Slack)
    payload = {
        "text": f"🚨 **{alert_data['alert_type']}** detected!\n"
                f"**Severity**: {alert_data['severity']} (Score: {alert_data['risk_score']})\n"
                f"**Transaction**: {alert_data['tx_hash']}\n"
                f"**Wallet**: {alert_data['wallet_address']}\n"
                f"**Details**: {alert_data['description']}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.webhook_url,
                json=payload,
                timeout=5.0
            )
            response.raise_for_status()
            logger.info(f"Successfully dispatched webhook for alert {alert_data['id']}")
    except httpx.HTTPError as e:
        logger.error(f"Failed to dispatch webhook for alert {alert_data['id']}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error dispatching webhook: {str(e)}")
