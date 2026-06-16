from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.bot.handlers import (
    start_handler,
    help_handler,
    clear_handler,
    message_handler,
    error_handler,
)

logger = get_logger(__name__)

_application: Application | None = None


def get_application() -> Application:
    global _application
    if _application is None:
        _application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .updater(None)          # Webhook mode — no polling
            .build()
        )

        # Register handlers
        _application.add_handler(CommandHandler("start", start_handler))
        _application.add_handler(CommandHandler("help", help_handler))
        _application.add_handler(CommandHandler("clear", clear_handler))
        _application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
        )
        _application.add_error_handler(error_handler)

        logger.info("Telegram Application initialized")
    return _application
