import asyncio
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Message

logger = get_logger(__name__)

_client: genai.Client | None = None

SYSTEM_PROMPT = """Sən AI fitness köməkçisisən.
ƏSAS QAYDA: İstifadəçi hansı dildə yazırsa, SƏN DƏ HƏMIN DİLDƏ cavab ver. Dili heç vaxt dəyişmə.
Qısa, aydın və faydalı cavablar ver."""


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


async def _with_retry(coro_fn, retries: int = 3, delay: float = 5.0):
    """503/429 xətalarında avtomatik yenidən cəhd edir."""
    for attempt in range(retries):
        try:
            return await coro_fn()
        except Exception as e:
            err = str(e)
            if attempt < retries - 1 and ("503" in err or "429" in err or "UNAVAILABLE" in err):
                wait = delay * (attempt + 1)
                logger.warning(f"Gemini {e.__class__.__name__}, {wait}s sonra yenidən cəhd ({attempt+1}/{retries})")
                await asyncio.sleep(wait)
            else:
                raise


async def generate_response(
    user_message: str,
    history: list[Message] | None = None,
) -> str:
    client = get_client()
    chat_history = _build_history(history) if history else []

    async def _call():
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

    try:
        return await _with_retry(_call)
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

    prompt = f"""İnternetdə aşağıdakı parametrlərə uyğun məşq proqramı axtar (muscleandstrength.com, bodybuilding.com, menshealth.com, myprotein.com kimi məşhur saytlarda):

- Həftədə məşq günü: {days} gün
- Məqsəd: {goal}
- Səviyyə: {level}
- Avadanlıq: {equipment}
- Fokus əzələ qrupu: {muscles}

Tapdığın ən uyğun proqramı Azərbaycan dilinde belə formatda ver:

🌐 *Mənbə:* [saytın adı və linki]

Sonra proqramı bu formatda yaz:
1. Hər gün üçün ayrıca başlıq (məs: 📅 Bazar ertəsi — Sinə + Triceps)
2. Hər məşq üçün: adı, set sayı, təkrar sayı, qısa izah
3. Sonda: istirahət və qidalanma məsləhəti (2-3 cümlə)

Markdown işarələri istifadə etmə. Sadə mətn və emoji ilə yaz."""

    async def _call():
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                max_output_tokens=2000,
                temperature=0.5,
            ),
        )
        return response.text or "Proqram hazırlanmadı."

    try:
        return await _with_retry(_call)
    except Exception as e:
        logger.error(f"Gemini workout error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e


async def edit_workout(program: str, instruction: str) -> str:
    """İstifadəçinin sərbəst mətnlə verdiyi təlimata (məs: 'Deadlift-i squat ilə əvəz et')
    uyğun olaraq mövcud məşq proqramını AI ilə dəyişir və tam yenilənmiş proqramı qaytarır."""
    client = get_client()

    prompt = f"""Aşağıda istifadəçinin mövcud məşq proqramı verilmişdir. İstifadəçinin tələbinə uyğun olaraq YALNIZ lazımi dəyişikliyi et, proqramın qalan hissəsini olduğu kimi saxla.

MÖVCUD PROQRAM:
{program}

İSTİFADƏÇİNİN TƏLƏBİ:
{instruction}

Qaydalar:
- Yalnız tələb olunan dəyişikliyi et, başqa heç nəyi dəyişmə.
- Proqramın strukturunu (gün başlıqları, set/təkrar formatı, emoji üslubu) saxla.
- Cavabında YALNIZ yenilənmiş tam proqramı ver — heç bir əlavə izahat, giriş və ya şərh yazma.
- Markdown işarələri istifadə etmə. Sadə mətn və emoji ilə yaz."""

    async def _call():
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3,
            ),
        )
        return response.text or program

    try:
        return await _with_retry(_call)
    except Exception as e:
        logger.error(f"Gemini edit_workout error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e
