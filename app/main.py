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


async def _init_bot_with_retry(application, retries: int = 5, delay: float = 5.0):
    """Telegram API-yə qoşulma zamanı timeout olarsa yenidən cəhd edir."""
    for attempt in range(retries):
        try:
            await application.initialize()
            await application.bot.set_webhook(
                url=settings.webhook_full_url,
                secret_token=settings.secret_token,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
            logger.info(f"Webhook set: {settings.webhook_full_url}")
            return
        except Exception as e:
            if attempt < retries - 1:
                wait = delay * (attempt + 1)
                logger.warning(f"Telegram qoşulma xətası: {e}. {wait}s sonra yenidən cəhd ({attempt+1}/{retries})")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Telegram qoşulma uğursuz oldu: {e}")
                raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    logger.info("Starting up...")

    await get_supabase()

    application = get_application()
    await _init_bot_with_retry(application)

    yield

    logger.info("Shutting down...")
    await application.shutdown()
    await close_supabase()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telegram AI Bot",
        description="AI-powered Telegram bot with FastAPI + Supabase + Gemini",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.include_router(health_router, tags=["health"])
    app.include_router(webhook_router, tags=["webhook"])

    return app


app = create_app()
