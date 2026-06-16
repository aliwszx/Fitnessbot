from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Message

logger = get_logger(__name__)

_client: genai.Client | None = None

SYSTEM_PROMPT = """Siz köməkçi bir AI fitness assistantısınız.
İstifadəçilərə Azərbaycan dilində, həmçinin onların öz dillərində cavab verin.
Qısa, aydın və faydalı cavablar verin."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(f"Gemini client initialized: {settings.gemini_model}")
    return _client


def _build_history(messages: list[Message]) -> list[types.Content]:
    history = []
    for msg in messages:
        role = "model" if msg.role == "assistant" else "user"
        history.append(
            types.Content(role=role, parts=[types.Part(text=msg.content)])
        )
    return history


async def generate_response(
    user_message: str,
    history: list[Message] | None = None,
) -> str:
    client = get_client()
    chat_history = _build_history(history) if history else []

    try:
        chat = client.aio.chats.create(
            model=settings.gemini_model,
            history=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
                temperature=0.7,
            ),
        )
        response = await chat.send_message(user_message)
        return response.text or "Cavab alınmadı."
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e


async def generate_workout(
    days: str,
    goal: str,
    level: str,
    equipment: str,
    muscles: str,
) -> str:
    client = get_client()

    prompt = f"""Aşağıdakı parametrlərə əsasən detallı həftəlik məşq proqramı hazırla:

- Həftədə məşq günü: {days} gün
- Məqsəd: {goal}
- Səviyyə: {level}
- Avadanlıq: {equipment}
- Fokus əzələ qrupu: {muscles}

Proqramı belə formatda ver:
1. Hər gün üçün ayrıca başlıq (məs: 📅 Bazar ertəsi — Sinə + Triceps)
2. Hər məşq üçün: adı, set sayı, təkrar sayı, qısa izah
3. Sonda: istirahət, qidalanma məsləhəti (2-3 cümlə)

Azərbaycan dilində yaz. Markdown formatından istifadə et."""

    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.8,
            ),
        )
        return response.text or "Proqram hazırlanmadı."
    except Exception as e:
        logger.error(f"Gemini workout error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e
