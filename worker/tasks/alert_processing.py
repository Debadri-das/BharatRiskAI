from backend.config.settings import get_settings
from backend.database.connection import get_supabase_admin_client
from backend.services.alert_delivery import deliver_alert


def process_alerts():
    settings = get_settings()
    destinations = []
    if settings.alert_webhook_url:
        destinations.append({"channel": "webhook", "destination": settings.alert_webhook_url})
    if settings.alert_sms_webhook_url:
        destinations.append({"channel": "sms_webhook", "destination": settings.alert_sms_webhook_url})
    if not destinations:
        return {"task": "alert_processing", "status": "waiting_for_destination"}

    zones = get_supabase_admin_client().table("zones").select("*").gte("risk_score", 76).execute().data
    deliveries = []
    for zone in zones:
        alert = {
            "alert_key": f"zone-{zone['id']}-{zone['risk_category']}",
            "zone_id": zone["id"],
            "zone_name": zone["name"],
            "alert_level": zone["risk_category"],
            "risk_score": zone["risk_score"],
            "generated_at": zone.get("updated_at"),
        }
        deliveries.extend(deliver_alert(alert, destinations))
    return {"task": "alert_processing", "status": "processed", "zones": len(zones), "deliveries": deliveries}
