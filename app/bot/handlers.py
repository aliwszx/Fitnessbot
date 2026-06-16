import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction

from app.core.logging import get_logger
from app.db.client import get_supabase
from app.db.repository import UserRepository, MessageRepository, WorkoutRepository
from app.db.models import UserCreate, MessageCreate, WorkoutCreate
from app.services.gemini_service import generate_response, generate_workout, edit_workout

logger = get_logger(__name__)

# ConversationHandler states
(
    CHOOSE_DAYS,
    CHOOSE_GOAL,
    CHOOSE_LEVEL,
    CHOOSE_EQUIPMENT,
    CHOOSE_MUSCLES,
    CONFIRM_WORKOUT,
    EDIT_CHOICE,
    EDIT_MANUAL_INPUT,
    EDIT_AI_INPUT,
) = range(9)


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


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Qəbul et", callback_data="confirm_accept"),
                InlineKeyboardButton("✏️ Redaktə et", callback_data="confirm_edit"),
            ]
        ]
    )


def _edit_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✍️ Özüm yazım", callback_data="edit_manual"),
                InlineKeyboardButton("🤖 AI ilə düzəlt", callback_data="edit_ai"),
            ],
            [InlineKeyboardButton("⬅️ Geri", callback_data="edit_back")],
        ]
    )


async def _send_program(message: Message, program: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    """Proqramı (lazım gəldikdə) hissələrə bölüb göndərir, klaviaturanı yalnız son hissəyə əlavə edir."""
    chunk_size = 3800
    chunks = [program[i:i + chunk_size] for i in range(0, len(program), chunk_size)] or [program]
    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        markup = keyboard if is_last else None
        try:
            await message.reply_text(chunk, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await message.reply_text(chunk, reply_markup=markup)


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
    except Exception as e:
        logger.error(f"Workout generation error: {e}")
        await query.message.reply_text("⚠️ Xəta baş verdi. /workout ilə yenidən cəhd edin.")
        context.user_data.pop("workout", None)
        return ConversationHandler.END

    # Draft kimi Supabase-də saxla — istifadəçi qəbul edənə qədər status 'draft' olaraq qalır
    user = update.effective_user
    db = await get_supabase()
    user_repo = UserRepository(db)
    workout_repo = WorkoutRepository(db)
    db_user = await user_repo.get_by_telegram_id(user.id) if user else None
    user_db_id = db_user.id if db_user else 0

    workout_row = await workout_repo.create(
        WorkoutCreate(
            user_id=user_db_id,
            telegram_id=user.id if user else 0,
            program=program,
            days=w["days"],
            goal=w["goal"],
            level=w["level"],
            equipment=w["equipment"],
            muscles=w["muscles"],
            status="draft",
        )
    )

    context.user_data["workout"]["program"] = program
    context.user_data["workout"]["workout_id"] = workout_row.id if workout_row else None

    await _send_program(query.message, program, keyboard=_confirm_keyboard())
    return CONFIRM_WORKOUT


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """'Qəbul et' / 'Redaktə et' düymələrini idarə edir."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_accept":
        workout_id = context.user_data.get("workout", {}).get("workout_id")
        if workout_id:
            db = await get_supabase()
            workout_repo = WorkoutRepository(db)
            await workout_repo.accept(workout_id)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text("✅ Məşq proqramı qəbul edildi və Supabase-də saxlanıldı!")
        context.user_data.pop("workout", None)
        return ConversationHandler.END

    # confirm_edit
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.reply_text(
        "Dəyişikliyi necə etmək istəyirsiniz?",
        reply_markup=_edit_choice_keyboard(),
    )
    return EDIT_CHOICE


async def edit_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """'Özüm yazım' / 'AI ilə düzəlt' / 'Geri' düymələrini idarə edir."""
    query = update.callback_query
    await query.answer()

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if query.data == "edit_back":
        program = context.user_data.get("workout", {}).get("program", "")
        await _send_program(query.message, program, keyboard=_confirm_keyboard())
        return CONFIRM_WORKOUT

    if query.data == "edit_manual":
        await query.message.reply_text("✍️ Yeni proqram mətnini tam şəkildə bura yazıb göndərin:")
        return EDIT_MANUAL_INPUT

    # edit_ai
    await query.message.reply_text(
        "🤖 Hansı dəyişikliyi etmək istəyirsiniz?\n\n"
        "Məsələn: \"Deadlift-i squat ilə əvəz et\" və ya \"Bazar ertəsi gününə daha bir məşq əlavə et\""
    )
    return EDIT_AI_INPUT


async def manual_edit_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """İstifadəçinin özünün yazdığı yeni proqram mətnini qəbul edir."""
    if not update.message or not update.message.text:
        return EDIT_MANUAL_INPUT

    new_program = update.message.text
    context.user_data.setdefault("workout", {})["program"] = new_program

    workout_id = context.user_data.get("workout", {}).get("workout_id")
    if workout_id:
        db = await get_supabase()
        workout_repo = WorkoutRepository(db)
        await workout_repo.update_program(workout_id, new_program, edit_type="manual")

    await update.message.reply_text("✅ Dəyişiklik qeyd edildi. Yenilənmiş proqram:")
    await _send_program(update.message, new_program, keyboard=_confirm_keyboard())
    return CONFIRM_WORKOUT


async def ai_edit_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """İstifadəçinin sərbəst mətnlə verdiyi dəyişiklik təlimatını AI-ya göndərir və proqramı yeniləyir."""
    if not update.message or not update.message.text:
        return EDIT_AI_INPUT

    instruction = update.message.text
    program = context.user_data.get("workout", {}).get("program", "")

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        new_program = await edit_workout(program, instruction)
    except Exception as e:
        logger.error(f"AI edit_workout error: {e}")
        await update.message.reply_text(
            "⚠️ Dəyişiklik edilərkən xəta baş verdi. Zəhmət olmasa yenidən cəhd edin."
        )
        return EDIT_AI_INPUT

    context.user_data.setdefault("workout", {})["program"] = new_program

    workout_id = context.user_data.get("workout", {}).get("workout_id")
    if workout_id:
        db = await get_supabase()
        workout_repo = WorkoutRepository(db)
        await workout_repo.update_program(workout_id, new_program, edit_type="ai")

    await update.message.reply_text("✅ AI dəyişikliyi tətbiq etdi. Yenilənmiş proqram:")
    await _send_program(update.message, new_program, keyboard=_confirm_keyboard())
    return CONFIRM_WORKOUT


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("workout", None)
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
