from fastapi import APIRouter
from backend.config.settings import get_settings
from backend.database.connection import check_database_connection
from backend.services.state_service import get_system_state

router = APIRouter()


@router.get("/health")
def health():
    settings = get_settings()
    state = get_system_state()
    try:
        database = check_database_connection()
    except Exception as error:
        database = {
            "configured": bool(settings.supabase_url and settings.supabase_key),
            "reachable": False,
            "error": str(error),
        }

    return {
        "status": state["status"],  # "READY" or "BLOCKED"
        "service": settings.app_name,
        "mode": settings.environment,
        "model_state": state["status"],
        "blocked_reason": state.get("blocked_reason"),
        "database": database,
        "artifacts": {
            "checkpoint": state.get("checkpoint_path"),
            "normalization": state.get("normalization_path"),
        },
        "validated_at": state.get("validated_at"),
    }


@router.get("/status")
def api_status():
    """Operational status endpoint returning system state and artifact metadata."""
    return get_system_state()
