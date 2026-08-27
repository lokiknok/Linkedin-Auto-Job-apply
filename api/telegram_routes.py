import logging
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
from telegram.notifier import telegram_notifier
from config import env_settings

logger = logging.getLogger("api.telegram")
router = APIRouter(prefix="/api/telegram", tags=["Telegram"])


@router.get("/status", response_model=Dict[str, Any])
def get_telegram_status():
    """Returns whether Telegram Bot token and chat ID are configured."""
    return {
        "configured": telegram_notifier.is_configured,
        "chat_id": telegram_notifier.chat_id if telegram_notifier.is_configured else None,
    }


@router.post("/test", response_model=Dict[str, Any])
def test_telegram_connection():
    """Sends a verification message to the configured Telegram chat."""
    result = telegram_notifier.test_connection()
    return result

