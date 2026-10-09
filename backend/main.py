import os
from pathlib import Path
from typing import Any, Dict

# 1. Environment Configuration: Dynamically resolve local repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent

ckpt_val = os.getenv("NOWCAST_CHECKPOINT", "models/checkpoints/best.pt")
norm_val = os.getenv("NOWCAST_NORMALIZATION", "models/preprocessing/scaler.json")

ckpt_path = Path(ckpt_val)
if not ckpt_path.is_absolute():
    ckpt_path = (REPO_ROOT / ckpt_path).resolve()

norm_path = Path(norm_val)
if not norm_path.is_absolute():
    norm_path = (REPO_ROOT / norm_path).resolve()

os.environ["NOWCAST_CHECKPOINT"] = str(ckpt_path)
os.environ["NOWCAST_NORMALIZATION"] = str(norm_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from backend.api import (
    dashboard,
    emergencies,
    health,
    nowcast,
    recommendations,
    reports,
    satellite,
    zones,
)
from backend.config.settings import get_settings
from backend.middleware.exposure_lock import ExposureLockMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.request_id import RequestIdMiddleware
from backend.services.state_service import (
    get_system_state,
    init_and_validate_system,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

# Middleware Stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(ExposureLockMiddleware)  # Enforces 503 on predictions/alerts if BLOCKED
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.on_event("startup")
def startup() -> None:
    """Validate model artifacts, checkpoint contracts, and initialize engine."""
    init_and_validate_system()


@app.get("/")
def root() -> Dict[str, Any]:
    """Root status endpoint returning operational state (READY vs BLOCKED)."""
    state = get_system_state()
    return {
        "service": settings.app_name,
        "status": state["status"],  # "READY" or "BLOCKED"
        "model_state": state["status"],
        "blocked_reason": state.get("blocked_reason"),
        "docs": "/docs",
        "api": "/api",
        "artifacts": {
            "checkpoint": state.get("checkpoint_path"),
            "normalization": state.get("normalization_path"),
        },
    }


@app.get("/status")
def status_endpoint() -> Dict[str, Any]:
    """Global system status endpoint."""
    return get_system_state()


@app.post("/api/status/revalidate")
def revalidate_endpoint() -> Dict[str, Any]:
    """Trigger runtime re-validation of model artifacts and refresh system state."""
    return init_and_validate_system()


for router in [
    health.router,
    nowcast.router,
    dashboard.router,
    zones.router,
    reports.router,
    emergencies.router,
    recommendations.router,
    satellite.router,
]:
    app.include_router(router, prefix="/api")
