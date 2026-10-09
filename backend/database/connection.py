import logging
from functools import lru_cache
from typing import Any, Dict

from backend.config.settings import get_settings
from backend.database.local_db import get_local_client

logger = logging.getLogger("bharatrisk.database")


def _is_demo_config(url: str, key: str) -> bool:
    """Check if the Supabase configuration uses dummy/demo credentials."""
    if not url or not key:
        return True
    u = url.lower()
    return "demo.supabase.co" in u or "localhost" in u or key in ("demo-key", "demo-service-key")


@lru_cache
def get_supabase_client() -> Any:
    """Initialize one backend client from environment settings, with graceful local fallback."""
    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_key

    if _is_demo_config(url, key):
        logger.info("Operating in demo/offline database mode with persistent local storage.")
        return get_local_client()

    try:
        from supabase import create_client
        client = create_client(url, key)
        # Verify remote connectivity
        client.table("zones").select("id", count="exact").limit(1).execute()
        return client
    except Exception as exc:
        logger.warning(f"Remote Supabase connection failed ({exc}). Falling back to resilient local database.")
        return get_local_client()


@lru_cache
def get_supabase_admin_client() -> Any:
    """Create the elevated backend client used for trusted maintenance jobs, with local fallback."""
    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_service_role_key or settings.supabase_key

    if _is_demo_config(url, key):
        return get_local_client()

    try:
        from supabase import create_client
        client = create_client(url, key)
        client.table("zones").select("id", count="exact").limit(1).execute()
        return client
    except Exception as exc:
        logger.warning(f"Remote Supabase admin connection failed ({exc}). Falling back to resilient local database.")
        return get_local_client()


def check_database_connection() -> Dict[str, Any]:
    """Run a read against the zones table for health checks and setup verification."""
    client = get_supabase_client()
    try:
        result = client.table("zones").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else len(result.data)
        is_local = hasattr(client, "_db")
        return {
            "configured": True,
            "reachable": True,
            "zone_count": count,
            "mode": "local_sqlite_json" if is_local else "supabase_remote",
        }
    except Exception as exc:
        return {
            "configured": False,
            "reachable": False,
            "error": str(exc),
        }


def get_db():
    yield get_supabase_client()


def get_admin_db():
    yield get_supabase_admin_client()
