import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from app.core.logging import get_logger
from app.db.client import get_supabase
from app.db.repository import UserRepository, MessageRepository
from app.db.models import UserCreate, MessageCreate
from app.services.gemini_service import generate_response

logger = get_logger(__name__)


async def _get_or_register_user(update: Update) -> None:
    """Register user in DB if not exists."""
    tg_user = update.effective_user
    if not tg_user:
        return

    db = await get_supabase()
    repo = UserRepository(db)
    await repo.get_or_create(
        UserCreate(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await _get_or_register_user(update)

    user = update.effective_user
    name = user.first_name if user else "İstifadəçi"

    await update.message.reply_text(
        f"Salam, {name}! 👋\n\n"
        "Mən AI köməkçinizəm. Hər hansı sualınızı yazın, kömək edəcəyəm.\n\n"
        "Əmrlər:\n"
        "/start — Başla\n"
        "/clear — Söhbəti təmizlə\n"
        "/help — Kömək",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "❓ *Kömək*\n\n"
        "Sadəcə mesaj yazın — AI cavab verəcək.\n\n"
        "*Əmrlər:*\n"
        "/start — Salamlama mesajı\n"
        "/clear — Söhbət tarixçəsini sil\n"
        "/help — Bu mesaj",
        parse_mode="Markdown",
    )


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command."""
    user = update.effective_user
    if not user:
        return

    db = await get_supabase()
    repo = MessageRepository(db)
    await repo.clear_history(user.id)

    await update.message.reply_text(
        "🗑️ Söhbət tarixçəniz silindi. Yeni söhbətə başlaya bilərsiniz."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    await _get_or_register_user(update)

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    user_text = update.message.text
    telegram_id = user.id

    db = await get_supabase()
    user_repo = UserRepository(db)
    msg_repo = MessageRepository(db)

    # Get DB user id
    db_user = await user_repo.get_by_telegram_id(telegram_id)
    user_db_id = db_user.id if db_user else 0

    # Get or create session id from context
    session_id = context.user_data.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        context.user_data["session_id"] = session_id

    # Save user message
    await msg_repo.save(
        MessageCreate(
            user_id=user_db_id,
            telegram_id=telegram_id,
            role="user",
            content=user_text,
            session_id=session_id,
        )
    )

    # Get history for context
    history = await msg_repo.get_history(telegram_id, session_id=session_id, limit=20)

    try:
        # Generate AI response
        ai_response = await generate_response(user_text, history[:-1])

        # Save assistant message
        await msg_repo.save(
            MessageCreate(
                user_id=user_db_id,
                telegram_id=telegram_id,
                role="assistant",
                content=ai_response,
                session_id=session_id,
            )
        )

        # Increment counter
        await user_repo.increment_message_count(telegram_id)

        await update.message.reply_text(ai_response)

    except RuntimeError as e:
        logger.error(f"Error generating response for {telegram_id}: {e}")
        await update.message.reply_text(
            "⚠️ Xəta baş verdi. Bir az sonra yenidən cəhd edin."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
