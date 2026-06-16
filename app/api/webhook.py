from fastapi import APIRouter, Request, HTTPException, status
from telegram import Update

from app.core.config import settings
from app.core.logging import get_logger
from app.bot.application import get_application

logger = get_logger(__name__)

router = APIRouter()


@router.post(f"/webhook/{settings.secret_token}")
async def telegram_webhook(request: Request) -> dict:
    """Receive updates from Telegram via webhook."""
    application = get_application()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    update = Update.de_json(body, application.bot)

    async with application:
        await application.process_update(update)

    return {"ok": True}
