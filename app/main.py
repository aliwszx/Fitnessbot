import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.client import get_supabase, close_supabase
from app.bot.application import get_application
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router

setup_logging()
logger = get_logger(__name__)


async def _set_webhook_background():
    """Server ayağa qalxdıqdan sonra arka planda webhook qurur."""
    await asyncio.sleep(3)  # Server tam başlayana qədər gözlə
    application = get_application()
    for attempt in range(10):
        try:
            await application.bot.set_webhook(
                url=settings.webhook_full_url,
                secret_token=settings.secret_token,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
            logger.info(f"Webhook quruldu: {settings.webhook_full_url}")
            return
        except Exception as e:
            wait = 10 * (attempt + 1)
            logger.warning(f"Webhook xətası: {e}. {wait}s sonra yenidən cəhd ({attempt+1}/10)")
            await asyncio.sleep(wait)
    logger.error("Webhook qurmaq uğursuz oldu.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up...")

    await get_supabase()

    application = get_application()
    await application.initialize()

    # Webhook-u arka planda qur — startup-u bloklamasın
    asyncio.create_task(_set_webhook_background())

    yield

    logger.info("Shutting down...")
    await application.shutdown()
    await close_supabase()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telegram AI Bot",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.include_router(health_router, tags=["health"])
    app.include_router(webhook_router, tags=["webhook"])

    return app


app = create_app()
