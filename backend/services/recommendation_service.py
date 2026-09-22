from supabase import Client
from backend.utils.geo import haversine_km


def recommendations_for_zone(db: Client, zone: dict) -> list[dict]:
    res = db.table("resources").select("*").gt("available", 0).execute()
    resources = res.data
    
    pop_factor = max(1, round(zone["population"] / 18000))
    critical = zone["risk_category"] == "CRITICAL"
    ranked = []

    def add(priority: int, action: str, resource_type: str, quantity: int, reason: str):
        ranked.append(
            {
                "priority": priority,
                "action": action,
                "resource_type": resource_type,
                "quantity": quantity,
                "reason": reason,
            }
        )

    if critical:
        add(1, "issue evacuation alert", "emergency_personnel", 1, f"{zone['name']} is critical with {zone['population']:,} people exposed.")
        add(2, "deploy rescue team", "rescue_team", min(3, pop_factor + 1), "Low elevation, heavy rainfall, and field reports raise rescue urgency.")
        add(3, "deploy boat", "boat", min(4, pop_factor + 1), "Waterlogging risk can block ground access in dense wards.")
    elif zone["risk_category"] == "HIGH":
        add(1, "deploy water pump", "water_pump", min(3, pop_factor), "High runoff and weak drainage can be reduced before the peak.")
        add(2, "open shelter", "shelter", 1, "Pre-position shelter capacity near the exposed population.")
    else:
        add(1, "monitor rainfall and drainage", "emergency_personnel", 1, "Risk is below emergency threshold but conditions can change quickly.")

    if zone["drainage_score"] < 45:
        add(len(ranked) + 1, "deploy water pump", "water_pump", min(4, pop_factor + 1), "Drainage efficiency is below 45 percent.")
    if zone["population"] > 30000:
        add(len(ranked) + 1, "deploy ambulance", "ambulance", 2, "Dense population requires medical standby and evacuation support.")
    add(len(ranked) + 1, "close vulnerable roads", "road_closure", 1, "Prevent traffic from entering flood-prone corridors.")

    for item in ranked:
        candidates = [r for r in resources if r["type"] == item["resource_type"]]
        if candidates:
            best = min(candidates, key=lambda r: haversine_km(zone["latitude"], zone["longitude"], r["latitude"], r["longitude"]))
            item["reason"] += f" Nearest available asset: {best['name']}."
    return ranked[:6]


def citywide_recommendations(db: Client) -> list[dict]:
    res = db.table("zones").select("*").order("risk_score", desc=True).limit(4).execute()
    zones = res.data
    output = []
    for zone in zones:
        for item in recommendations_for_zone(db, zone)[:3]:
            output.append({"zone_id": zone["id"], "zone_name": zone["name"], **item})
    return sorted(output, key=lambda row: (row["priority"], -len(row["reason"])))[:10]
