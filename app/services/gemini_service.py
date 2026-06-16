import asyncio
import re
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Message

logger = get_logger(__name__)

_client: genai.Client | None = None

SYSTEM_PROMPT = """Sən 30 illik təcrübəyə malik peşəkar fitness məşqçisisən (sertifikatlı şəxsi məşqçi və qidalanma üzrə bilikli mütəxəssis).
ƏSAS QAYDA: İstifadəçi hansı dildə yazırsa, SƏN DƏ HƏMIN DİLDƏ cavab ver. Dili heç vaxt dəyişmə.
Bütün suallara dəqiq, düzgün və lazım gəldikdə qısa izahla cavab ver — bir məşqçinin öz şagirdinə izah etdiyi kimi aydın və etibarlı ol. Sözü uzatma, amma vacib detalı əsla buraxma."""

# Əsas model əvəzinə sınanacaq fallback modellərin sırası.
# Gündəlik kvota bitdikdə növbəti modelə keçilir.
_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Gündəlik kvota xətası üçün istifadəçiyə göstəriləcək mesaj
_QUOTA_MSG = (
    "⚠️ Gündəlik AI limiti dolub. Bir neçə saat sonra yenidən cəhd edin."
)


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


def _is_daily_quota(err: str) -> bool:
    """Gündəlik kvota bitibsə True qaytarır (retry faydasızdır)."""
    return "GenerateRequestsPerDayPerProject" in err or "free_tier_requests" in err


def _retry_after_seconds(err: str) -> float | None:
    """429 cavabındakı retryDelay-i saniyə olaraq oxuyur."""
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", err)
    if m:
        return float(m.group(1))
    return None


async def _with_retry(coro_fn, model: str, retries: int = 3, delay: float = 10.0):
    """503/429 xətalarında avtomatik yenidən cəhd edir.
    Gündəlik kvota bitibsə fallback modelə keçir."""
    models_to_try = [model] + _FALLBACK_MODELS

    for current_model in models_to_try:
        for attempt in range(retries):
            try:
                return await coro_fn(current_model)
            except Exception as e:
                err = str(e)
                is_429 = "429" in err or "RESOURCE_EXHAUSTED" in err
                is_503 = "503" in err or "UNAVAILABLE" in err

                if is_429 and _is_daily_quota(err):
                    # Gündəlik kvota bitib — bu modeli tamam burax, növbətinə keç
                    logger.warning(
                        f"Gündəlik kvota bitdi ({current_model}), "
                        f"fallback modelə keçilir..."
                    )
                    break  # inner loop-dan çıx, növbəti model sınanır

                if attempt < retries - 1 and (is_429 or is_503):
                    # Rate limit (saniyəlik/dəqiqəlik) — qısa gözlə, retry et
                    sug = _retry_after_seconds(err)
                    wait = sug if sug and sug < 60 else delay * (attempt + 1)
                    logger.warning(
                        f"Gemini {e.__class__.__name__} ({current_model}), "
                        f"{wait:.1f}s sonra yenidən cəhd ({attempt+1}/{retries})"
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        else:
            # retries tükəndi amma gündəlik kvota xətası deyildi — raise
            continue
        # inner loop `break` ilə bitdi (gündəlik kvota) — növbəti model

    # Bütün modellər tükəndi
    raise RuntimeError(_QUOTA_MSG)


async def generate_response(
    user_message: str,
    history: list[Message] | None = None,
) -> str:
    client = get_client()
    chat_history = _build_history(history) if history else []

    def _call(model: str):
        async def _inner():
            chat = client.aio.chats.create(
                model=model,
                history=chat_history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1500,
                    temperature=0.7,
                ),
            )
            response = await chat.send_message(user_message)
            return response.text or "Cavab alınmadı."
        return _inner()

    try:
        return await _with_retry(_call, settings.gemini_model)
    except RuntimeError:
        raise
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

    prompt = f"""Sən 30 illik təcrübəyə malik peşəkar fitness məşqçisisən (sertifikatlı şəxsi məşqçi). İstifadəçinin aşağıdakı parametrlərinə tam uyğun, öz peşəkar bilik və təcrübənə əsaslanan fərdi məşq proqramı SƏN ÖZÜN hazırla.

Parametrlər:
- Həftədə məşq günü: {days} gün
- Məqsəd: {goal}
- Səviyyə: {level}
- Avadanlıq: {equipment}
- Fokus əzələ qrupu: {muscles}

Tələblər:
- Heç bir konkret veb-saytdan və ya mənbədən köçürmə; mənbə, link və ya sayt adı QƏTİYYƏN YAZMA.
- Hərəkət seçimi, set/təkrar sayları və istirahət vaxtları məqsədə və səviyyəyə tam uyğun, elmi əsaslı və düzgün olsun.
- Hər hərəkətin yanında nə üçün seçildiyini 1 qısa cümlə ilə izah et (təcrübəli məşqçi məntiqi ilə).
- Sonda 2-3 cümləlik düzgün istirahət və qidalanma tövsiyəsi ver.

Format:
1. Hər gün üçün ayrıca başlıq (məs: 📅 Bazar ertəsi — Sinə + Triceps)
2. Hər hərəkət üçün: adı, set sayı, təkrar sayı, qısa izah
3. Sonda: istirahət və qidalanma tövsiyəsi

Markdown işarələri istifadə etmə. Sadə mətn və emoji ilə yaz."""

    def _call(model: str):
        async def _inner():
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=4096,
                    temperature=0.6,
                ),
            )
            return response.text or "Proqram hazırlanmadı."
        return _inner()

    try:
        return await _with_retry(_call, settings.gemini_model)
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Gemini workout error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e


async def edit_workout(program: str, instruction: str) -> str:
    """İstifadəçinin sərbəst mətnlə verdiyi təlimata uyğun olaraq
    mövcud məşq proqramını AI ilə dəyişir və tam yenilənmiş proqramı qaytarır."""
    client = get_client()

    prompt = f"""Sən 30 illik təcrübəyə malik peşəkar fitness məşqçisisən. Aşağıda istifadəçinin mövcud məşq proqramı verilmişdir. İstifadəçinin tələbinə uyğun olaraq YALNIZ lazımi dəyişikliyi peşəkar məşqçi məntiqi ilə et (məs. əvəz olunan hərəkət bənzər əzələ qrupuna və çətinlik səviyyəsinə uyğun olsun), proqramın qalan hissəsini olduğu kimi saxla.

MÖVCUD PROQRAM:
{program}

İSTİFADƏÇİNİN TƏLƏBİ:
{instruction}

Qaydalar:
- Yalnız tələb olunan dəyişikliyi et, başqa heç nəyi dəyişmə.
- Proqramın strukturunu (gün başlıqları, set/təkrar formatı, emoji üslubu) saxla.
- Mənbə, link və ya sayt adı yazma.
- Cavabında YALNIZ yenilənmiş tam proqramı ver — heç bir əlavə izahat, giriş və ya şərh yazma.
- Markdown işarələri istifadə etmə. Sadə mətn və emoji ilə yaz."""

    def _call(model: str):
        async def _inner():
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=4096,
                    temperature=0.3,
                ),
            )
            return response.text or program
        return _inner()

    try:
        return await _with_retry(_call, settings.gemini_model)
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Gemini edit_workout error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e
