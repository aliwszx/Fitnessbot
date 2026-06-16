import asyncio
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException, status
from telegram import Update

from app.core.config import settings
from app.core.logging import get_logger
from app.bot.application import get_application

logger = get_logger(__name__)

router = APIRouter()

# Telegram-ın retry etməsinin qarşısını almaq üçün emal edilmiş
# update_id-ləri saxlayırıq. Set thread-safe deyil, amma asyncio
# single-threaded olduğundan burada problem yoxdur.
_processed_update_ids: set[int] = set()
_MAX_CACHE_SIZE = 1000  # yaddaş sızmasının qarşısını almaq üçün


async def _process_update_background(update: Update) -> None:
    """Update-i background-da emal et ki, Telegram 200 OK alsın."""
    application = get_application()
    try:
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Update emalında xəta (update_id={update.update_id}): {e}")


@router.post(f"/webhook/{settings.secret_token}")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
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

    # Telegram-ın retry etdiyi dublikat update-ləri ötür
    if update.update_id in _processed_update_ids:
        logger.warning(f"Dublikat update atlandı: update_id={update.update_id}")
        return {"ok": True}

    # Cache-i idarə et
    _processed_update_ids.add(update.update_id)
    if len(_processed_update_ids) > _MAX_CACHE_SIZE:
        # Ən kiçik (ən köhnə) ID-ləri sil
        oldest = sorted(_processed_update_ids)[:100]
        for uid in oldest:
            _processed_update_ids.discard(uid)

    # application artıq lifespan-da initialize olub —
    # async with application: BU YERdə İŞLƏNMƏMƏLİDİR.
    # Hər request-də initialize()/shutdown() çağırıb state toqquşmasına
    # səbəb olur. Update-i background task olaraq emal edirik ki,
    # Telegram dərhal 200 OK alsın və retry etməsin.
    background_tasks.add_task(_process_update_background, update)

    return {"ok": True}
