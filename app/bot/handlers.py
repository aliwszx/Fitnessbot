import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction

from app.core.logging import get_logger
from app.db.client import get_supabase
from app.db.repository import UserRepository, MessageRepository
from app.db.models import UserCreate, MessageCreate
from app.services.gemini_service import generate_response, generate_workout

logger = get_logger(__name__)

# ConversationHandler states
CHOOSE_DAYS, CHOOSE_GOAL, CHOOSE_LEVEL, CHOOSE_EQUIPMENT, CHOOSE_MUSCLES = range(5)


async def _get_or_register_user(update: Update) -> None:
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
    await _get_or_register_user(update)
    user = update.effective_user
    name = user.first_name if user else "İstifadəçi"
    await update.message.reply_text(
        f"Salam, {name}! 👋\n\n"
        "Mən AI fitness köməkçinizəm. Hər hansı sualınızı yazın.\n\n"
        "Əmrlər:\n"
        "/start — Başla\n"
        "/workout — 💪 Məşq proqramı al\n"
        "/clear — Söhbəti təmizlə\n"
        "/help — Kömək",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ *Kömək*\n\n"
        "Sadəcə mesaj yazın — AI cavab verəcək.\n\n"
        "*Əmrlər:*\n"
        "/start — Salamlama mesajı\n"
        "/workout — 💪 Məşq proqramı al\n"
        "/clear — Söhbət tarixçəsini sil\n"
        "/help — Bu mesaj",
        parse_mode="Markdown",
    )


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    db = await get_supabase()
    repo = MessageRepository(db)
    await repo.clear_history(user.id)
    await update.message.reply_text("🗑️ Söhbət tarixçəniz silindi.")


# ─── WORKOUT CONVERSATION ───────────────────────────────────────────────────

async def workout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start workout flow — ask days per week."""
    context.user_data["workout"] = {}
    keyboard = [
        [
            InlineKeyboardButton("3 gün", callback_data="days_3"),
            InlineKeyboardButton("4 gün", callback_data="days_4"),
            InlineKeyboardButton("5 gün", callback_data="days_5"),
        ]
    ]
    await update.message.reply_text(
        "💪 *Məşq Proqramı*\n\nHəftədə neçə gün məşq etmək istəyirsiniz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSE_DAYS


async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    days = query.data.split("_")[1]
    context.user_data["workout"]["days"] = days

    keyboard = [
        [
            InlineKeyboardButton("🏋️ Kütlə qazanmaq", callback_data="goal_mass"),
            InlineKeyboardButton("🔥 Yağ yandırmaq", callback_data="goal_cut"),
        ],
        [
            InlineKeyboardButton("💪 Güc artırmaq", callback_data="goal_strength"),
            InlineKeyboardButton("⚖️ Forma saxlamaq", callback_data="goal_maintain"),
        ],
    ]
    await query.edit_message_text(
        f"✅ *{days} gün/həftə* seçildi.\n\nMəqsədiniz nədir?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSE_GOAL


async def goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    goal_map = {
        "goal_mass": "Kütlə qazanmaq",
        "goal_cut": "Yağ yandırmaq",
        "goal_strength": "Güc artırmaq",
        "goal_maintain": "Forma saxlamaq",
    }
    context.user_data["workout"]["goal"] = goal_map[query.data]

    keyboard = [
        [
            InlineKeyboardButton("🌱 Başlanğıc", callback_data="level_beginner"),
            InlineKeyboardButton("🔶 Orta", callback_data="level_intermediate"),
            InlineKeyboardButton("🔴 İrəli", callback_data="level_advanced"),
        ]
    ]
    await query.edit_message_text(
        f"✅ *{goal_map[query.data]}* seçildi.\n\nSəviyyəniz nədir?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSE_LEVEL


async def level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    level_map = {
        "level_beginner": "Başlanğıc",
        "level_intermediate": "Orta",
        "level_advanced": "İrəli",
    }
    context.user_data["workout"]["level"] = level_map[query.data]

    keyboard = [
        [
            InlineKeyboardButton("🏠 Ev (avadanlıqsız)", callback_data="eq_home"),
            InlineKeyboardButton("🏋️ Zal (tam avadanlıq)", callback_data="eq_gym"),
        ],
        [
            InlineKeyboardButton("🔩 Minimal (halter/çəki)", callback_data="eq_minimal"),
        ],
    ]
    await query.edit_message_text(
        f"✅ *{level_map[query.data]}* seçildi.\n\nAvadanlıq vəziyyətiniz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSE_EQUIPMENT


async def equipment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    eq_map = {
        "eq_home": "Ev (avadanlıqsız)",
        "eq_gym": "Zal (tam avadanlıq)",
        "eq_minimal": "Minimal (halter/çəki)",
    }
    context.user_data["workout"]["equipment"] = eq_map[query.data]

    keyboard = [
        [
            InlineKeyboardButton("🫁 Sinə", callback_data="m_chest"),
            InlineKeyboardButton("🔙 Arxa", callback_data="m_back"),
            InlineKeyboardButton("🦵 Ayaq", callback_data="m_legs"),
        ],
        [
            InlineKeyboardButton("💪 Biceps/Triceps", callback_data="m_arms"),
            InlineKeyboardButton("🎯 Çiyin", callback_data="m_shoulders"),
            InlineKeyboardButton("🔥 Qarın", callback_data="m_abs"),
        ],
        [
            InlineKeyboardButton("✅ Bütün bədən", callback_data="m_fullbody"),
        ],
    ]
    await query.edit_message_text(
        f"✅ *{eq_map[query.data]}* seçildi.\n\nHansi əzələlərə fokuslanmaq istəyirsiniz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CHOOSE_MUSCLES


async def muscles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    muscle_map = {
        "m_chest": "Sinə",
        "m_back": "Arxa",
        "m_legs": "Ayaq",
        "m_arms": "Biceps/Triceps",
        "m_shoulders": "Çiyin",
        "m_abs": "Qarın",
        "m_fullbody": "Bütün bədən",
    }
    context.user_data["workout"]["muscles"] = muscle_map[query.data]

    await query.edit_message_text("⏳ AI məşq proqramınızı hazırlayır...")
    await query.message.chat.send_action(ChatAction.TYPING)

    w = context.user_data["workout"]
    try:
        program = await generate_workout(
            days=w["days"],
            goal=w["goal"],
            level=w["level"],
            equipment=w["equipment"],
            muscles=w["muscles"],
        )
        # Telegram 4096 simvol limiti var, uzun mətnləri hissələrə böl
        chunk_size = 3800
        for i in range(0, len(program), chunk_size):
            chunk = program[i:i + chunk_size]
            try:
                await query.message.reply_text(chunk, parse_mode="MarkdownV2")
            except Exception:
                await query.message.reply_text(chunk)
    except Exception as e:
        logger.error(f"Workout generation error: {e}")
        await query.message.reply_text("⚠️ Xəta baş verdi. /workout ilə yenidən cəhd edin.")

    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Məşq proqramı ləğv edildi.")
    return ConversationHandler.END


# ─── GENERAL MESSAGE ────────────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not user:
        return

    await _get_or_register_user(update)
    await update.message.chat.send_action(ChatAction.TYPING)

    user_text = update.message.text
    telegram_id = user.id

    db = await get_supabase()
    user_repo = UserRepository(db)
    msg_repo = MessageRepository(db)

    db_user = await user_repo.get_by_telegram_id(telegram_id)
    user_db_id = db_user.id if db_user else 0

    session_id = context.user_data.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        context.user_data["session_id"] = session_id

    await msg_repo.save(
        MessageCreate(
            user_id=user_db_id,
            telegram_id=telegram_id,
            role="user",
            content=user_text,
            session_id=session_id,
        )
    )

    history = await msg_repo.get_history(telegram_id, session_id=session_id, limit=20)

    try:
        ai_response = await generate_response(user_text, history[:-1])
        await msg_repo.save(
            MessageCreate(
                user_id=user_db_id,
                telegram_id=telegram_id,
                role="assistant",
                content=ai_response,
                session_id=session_id,
            )
        )
        await user_repo.increment_message_count(telegram_id)
        await update.message.reply_text(ai_response)
    except RuntimeError as e:
        logger.error(f"Error generating response for {telegram_id}: {e}")
        await update.message.reply_text("⚠️ Xəta baş verdi. Bir az sonra yenidən cəhd edin.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)
