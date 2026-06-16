import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Message

logger = get_logger(__name__)

_model: genai.GenerativeModel | None = None

SYSTEM_PROMPT = """Siz köməkçi bir AI assistantısınız.
İstifadəçilərə Azərbaycan dilində, həmçinin onların öz dillərində cavab verin.
Qısa, aydın və faydalı cavablar verin."""

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


def get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_PROMPT,
            safety_settings=SAFETY_SETTINGS,
        )
        logger.info(f"Gemini model initialized: {settings.gemini_model}")
    return _model


def _build_history(messages: list[Message]) -> list[dict]:
    """Convert DB messages to Gemini chat history format."""
    history = []
    for msg in messages:
        # Gemini uses "user" and "model" roles
        role = "model" if msg.role == "assistant" else "user"
        history.append({"role": role, "parts": [msg.content]})
    return history


async def generate_response(
    user_message: str,
    history: list[Message] | None = None,
) -> str:
    model = get_model()

    # Build history excluding the last user message (we send it separately)
    chat_history = _build_history(history) if history else []

    try:
        chat = model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            user_message,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1000,
                temperature=0.7,
            ),
        )
        return response.text or "Cavab alınmadı."
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"AI xəta: {e}") from e
