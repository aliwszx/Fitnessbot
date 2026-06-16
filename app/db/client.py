from supabase import AsyncClient, acreate_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_supabase: AsyncClient | None = None


async def get_supabase() -> AsyncClient:
    global _supabase
    if _supabase is None:
        _supabase = await acreate_client(
            settings.supabase_url,
            settings.supabase_key,
        )
        logger.info("Supabase async client initialized")
    return _supabase


async def close_supabase() -> None:
    global _supabase
    if _supabase is not None:
        # aclose() yoxdur, sadəcə None et
        _supabase = None
        logger.info("Supabase client closed")
