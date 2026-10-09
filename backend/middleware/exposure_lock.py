"""
Exposure Lock Middleware.
Prevents downstream consumption of predictions or alerts when the system is in a BLOCKED state.
Returns HTTP 503 Service Unavailable on all prediction and alert endpoints if artifacts are unverified.
"""
from __future__ import annotations

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.services.state_service import get_system_state

logger = logging.getLogger("bharatrisk.exposure_lock")


class ExposureLockMiddleware(BaseHTTPMiddleware):
    """Enforce strict exposure locking across prediction and alert endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Endpoints subject to Exposure Lock:
        # - Any nowcasting prediction routes: /api/nowcast/city, /api/nowcast/zone/*
        # - Any alert routes: /api/nowcast/alerts, /alerts
        is_prediction_or_alert = (
            path.startswith("/api/nowcast")
            or path.startswith("/nowcast")
            or "/alerts" in path
        )

        if is_prediction_or_alert:
            state = get_system_state()
            if state.get("status") != "READY":
                reason = state.get("blocked_reason") or "Model artifacts missing or invalid"
                logger.warning(
                    f"ExposureLock triggered for {request.method} {path} - System state: BLOCKED ({reason})"
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "BLOCKED",
                        "error": "Service Unavailable",
                        "detail": (
                            f"System state is BLOCKED. Nowcasting prediction and alert endpoints "
                            f"are locked to prevent downstream consumption of invalid inferences. "
                            f"Reason: {reason}"
                        ),
                        "blocked_reason": reason,
                        "checkpoint": state.get("checkpoint_path"),
                        "normalization": state.get("normalization_path"),
                        "validated_at": state.get("validated_at"),
                    },
                )

        return await call_next(request)
