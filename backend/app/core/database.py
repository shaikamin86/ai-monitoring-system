from typing import Optional
from supabase import create_client, Client
from app.core.config import settings
import structlog

log = structlog.get_logger()

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        log.info("Supabase client initialized")
    return _client


def get_anon_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
