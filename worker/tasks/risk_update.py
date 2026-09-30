from typing import Any, Iterable

from backend.services.nowcast_service import validate_nowcast_output


def update_risk(nowcast_outputs: Iterable[dict[str, Any]] | None = None):
    """Consume only validated model outputs; never report readiness by default."""
    if nowcast_outputs is None:
        return {"task": "risk_update", "status": "BLOCKED", "blocked_reason": "no validated nowcast outputs supplied"}
    outputs = list(nowcast_outputs)
    blocked = [validate_nowcast_output(item) for item in outputs]
    blocked = [reason for reason in blocked if reason]
    if blocked:
        return {"task": "risk_update", "status": "BLOCKED", "blocked_reason": blocked[0], "validated": 0}
    return {"task": "risk_update", "status": "READY", "validated": len(outputs)}
