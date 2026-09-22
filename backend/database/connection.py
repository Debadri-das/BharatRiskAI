from functools import lru_cache

from supabase import create_client, Client
from backend.config.settings import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Initialize one backend-only Supabase client from environment settings."""
    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_key

    if not url or not key:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in .env.")

    return create_client(url, key)


@lru_cache
def get_supabase_admin_client() -> Client:
    """Create the elevated backend client used only for trusted maintenance jobs."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase admin access is not configured. Set SUPABASE_SERVICE_ROLE_KEY in .env.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def check_database_connection() -> dict:
    """Run a cheap read against the zones table for health checks and setup verification."""
    result = get_supabase_client().table("zones").select("id", count="exact").limit(1).execute()
    return {"configured": True, "reachable": True, "zone_count": result.count or 0}


def get_db():
    yield get_supabase_client()


def get_admin_db():
    yield get_supabase_admin_client()
