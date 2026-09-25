import asyncio
from supabase import acreate_client, AsyncClient
from config import settings
import logging

logger = logging.getLogger(__name__)

# Initialised in lifespan via init_supabase() — None until then.
supabase: AsyncClient | None = None


async def init_supabase():
    global supabase
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.error("Supabase credentials not found. Ensure SUPABASE_URL and SUPABASE_KEY are set.")
        raise ValueError("Missing Supabase credentials.")
    supabase = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    logger.info("Async Supabase client initialised")


async def ping(timeout_seconds: float = 5.0) -> bool:
    """Return True if Supabase answers a trivial query within the timeout."""
    if supabase is None:
        return False
    try:
        await asyncio.wait_for(
            supabase.table("users").select("id").limit(1).execute(),
            timeout=timeout_seconds,
        )
        return True
    except Exception:
        logger.exception("Supabase health ping failed")
        return False
