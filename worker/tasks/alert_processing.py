from backend.config.settings import get_settings
from backend.database.connection import get_supabase_admin_client
from backend.services.alert_delivery import deliver_alert
from backend.services.nowcast_service import validate_nowcast_output


def process_alerts(nowcast_outputs=None):
    settings = get_settings()
    if nowcast_outputs is None:
        return {"task": "alert_processing", "status": "BLOCKED", "blocked_reason": "no validated nowcast outputs supplied", "deliveries": []}
    outputs = list(nowcast_outputs)
    if not outputs:
        return {"task": "alert_processing", "status": "BLOCKED", "blocked_reason": "no validated nowcast outputs supplied", "deliveries": []}

    invalid = next((validate_nowcast_output(item.get("nowcast") if "nowcast" in item else item) for item in outputs), None)
    if invalid:
        return {"task": "alert_processing", "status": "BLOCKED", "blocked_reason": invalid, "deliveries": []}

    destinations = []
    if settings.alert_webhook_url:
        destinations.append({"channel": "webhook", "destination": settings.alert_webhook_url})
    if settings.alert_sms_webhook_url:
        destinations.append({"channel": "sms_webhook", "destination": settings.alert_sms_webhook_url})
    if not destinations:
        return {"task": "alert_processing", "status": "waiting_for_destination"}

    deliveries = []
    for item in outputs:
        prediction = item.get("nowcast", item)
        calibrated = prediction.get("calibrated_alert") or {}
        alert_level = calibrated.get("alert_level", prediction.get("alert_level"))
        if alert_level not in ("RED", "ORANGE", "YELLOW"):
            continue
        alert = {
            "alert_key": f"zone-{item['zone_id']}-{alert_level}",
            "zone_id": item["zone_id"], "zone_name": item.get("zone_name"),
            "alert_level": alert_level,
            "primary_hazard": calibrated.get("primary_hazard", prediction["primary_hazard"]),
            "lead_time_minutes": calibrated.get("lead_time_minutes", prediction.get("lead_time_minutes")),
            "peak_interval": calibrated.get("peak_interval", prediction.get("peak_interval")),
            "advisory": calibrated.get("advisory", prediction.get("advisory")),
            "calibration_status": calibrated.get("calibration_status", prediction.get("calibration_status", "UNSPECIFIED")),
            "generated_at": item.get("generated_at"),
        }
        deliveries.extend(deliver_alert(alert, destinations))
    return {"task": "alert_processing", "status": "processed", "zones": len(outputs), "deliveries": deliveries}
