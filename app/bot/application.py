from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
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
    workout_handler,
    days_callback,
    goal_callback,
    level_callback,
    equipment_callback,
    muscles_callback,
    confirm_callback,
    edit_choice_callback,
    manual_edit_input_handler,
    ai_edit_input_handler,
    cancel_handler,
    CHOOSE_DAYS, CHOOSE_GOAL, CHOOSE_LEVEL, CHOOSE_EQUIPMENT, CHOOSE_MUSCLES,
    CONFIRM_WORKOUT, EDIT_CHOICE, EDIT_MANUAL_INPUT, EDIT_AI_INPUT,
)

logger = get_logger(__name__)

_application: Application | None = None


def get_application() -> Application:
    global _application
    if _application is None:
        _application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .updater(None)
            .build()
        )

        # Workout conversation handler
        workout_conv = ConversationHandler(
            entry_points=[CommandHandler("workout", workout_handler)],
            states={
                CHOOSE_DAYS: [CallbackQueryHandler(days_callback, pattern="^days_")],
                CHOOSE_GOAL: [CallbackQueryHandler(goal_callback, pattern="^goal_")],
                CHOOSE_LEVEL: [CallbackQueryHandler(level_callback, pattern="^level_")],
                CHOOSE_EQUIPMENT: [CallbackQueryHandler(equipment_callback, pattern="^eq_")],
                CHOOSE_MUSCLES: [CallbackQueryHandler(muscles_callback, pattern="^m_")],
                CONFIRM_WORKOUT: [CallbackQueryHandler(confirm_callback, pattern="^confirm_")],
                EDIT_CHOICE: [CallbackQueryHandler(edit_choice_callback, pattern="^edit_")],
                EDIT_MANUAL_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, manual_edit_input_handler)
                ],
                EDIT_AI_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, ai_edit_input_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel_handler)],
        )

        _application.add_handler(CommandHandler("start", start_handler))
        _application.add_handler(CommandHandler("help", help_handler))
        _application.add_handler(CommandHandler("clear", clear_handler))
        _application.add_handler(workout_conv)
        _application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
        )
        _application.add_error_handler(error_handler)

        logger.info("Telegram Application initialized")
    return _application
