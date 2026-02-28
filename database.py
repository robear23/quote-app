from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    """Initialize and return the Supabase client."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.error("Supabase credentials not found. Ensure SUPABASE_URL and SUPABASE_KEY are set.")
        raise ValueError("Missing Supabase credentials.")
        
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

supabase: Client = get_supabase_client()
