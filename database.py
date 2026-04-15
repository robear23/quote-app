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
