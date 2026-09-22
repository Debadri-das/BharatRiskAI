from fastapi import APIRouter
from backend.config.settings import get_settings
from backend.database.connection import check_database_connection

router = APIRouter()


@router.get("/health")
def health():
    settings = get_settings()
    try:
        database = check_database_connection()
        return {"status": "ok", "service": settings.app_name, "mode": settings.environment, "database": database}
    except Exception as error:
        return {"status": "degraded", "service": settings.app_name, "mode": settings.environment, "database": {"configured": bool(settings.supabase_url and settings.supabase_key), "reachable": False, "error": str(error)}}
