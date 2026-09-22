"""
Nowcasting & Early Warning Service.
Integrates live weather observation ingestion, convective instability models,
and generates hyper-local 0-6h predictions, alert levels, and lead times.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from supabase import Client

from ingestion.satellite_feeds import latest_satellite_observation
from ml.nowcasting.model import WeatherNowcastModel


_nowcast_engine = WeatherNowcastModel()


def get_zone_nowcast(db: Client, zone_id: int, live: bool = True) -> Optional[Dict[str, Any]]:
    """Generate hyper-local 0-6h severe weather nowcast for a specific zone."""
    res = db.table("zones").select("*").eq("id", zone_id).execute()
    if not res.data:
        return None
    zone = res.data[0]

    # Satellite products are refreshed by the worker and decoded for this request path.
    obs = latest_satellite_observation()
    
    # Merge zone physical parameters
    obs["elevation"] = zone["elevation"]
    obs["drainage_score"] = zone["drainage_score"]
    obs["population"] = zone["population"]
    obs["rainfall_24h"] = max(zone["rainfall_24h"], obs.get("rainfall_24h", 0))

    prediction = _nowcast_engine.predict_nowcast(obs)

    return {
        "zone_id": zone["id"],
        "zone_name": zone["name"],
        "latitude": zone["latitude"],
        "longitude": zone["longitude"],
        "current_weather": {
            "rainfall_15m_rate": obs.get("rainfall_15m_rate", 24.0),
            "temperature_c": obs.get("temperature_c", 28.0),
            "humidity_percent": obs.get("humidity_percent", 88.0),
            "wind_speed_kmh": obs.get("wind_speed_kmh", 25.0),
            "radar_reflectivity_dbz": obs.get("radar_reflectivity_dbz", 35.0),
            "cape_j_kg": obs.get("cape_j_kg", 1500.0),
        },
        "nowcast": prediction,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_citywide_nowcast(db: Client, live: bool = True) -> Dict[str, Any]:
    """Aggregate nowcasting across all monitored wards/zones with active early warnings."""
    res = db.table("zones").select("*").execute()
    zones = res.data
    zone_nowcasts = []
    active_alerts = []
    
    max_city_rain_rate = 0.0
    highest_alert = "GREEN"
    alert_rank = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}

    for zone in zones:
        zn = get_zone_nowcast(db, zone["id"], live=live)
        if not zn:
            continue
        zone_nowcasts.append(zn)
        
        ncast = zn["nowcast"]
        alert = ncast["alert_level"]
        
        if alert_rank.get(alert, 0) > alert_rank.get(highest_alert, 0):
            highest_alert = alert
            
        if ncast["max_rain_rate_mm_hr"] > max_city_rain_rate:
            max_city_rain_rate = ncast["max_rain_rate_mm_hr"]

        if alert in ("RED", "ORANGE", "YELLOW"):
            active_alerts.append({
                "zone_id": zone["id"],
                "zone_name": zone["name"],
                "alert_level": alert,
                "primary_hazard": ncast["primary_hazard"],
                "lead_time_minutes": ncast["lead_time_minutes"],
                "peak_interval": ncast["peak_interval"],
                "rain_rate_mm_hr": ncast["max_rain_rate_mm_hr"],
                "advisory": ncast["advisory"],
            })

    # Sort alerts by severity descending
    active_alerts.sort(key=lambda a: (alert_rank.get(a["alert_level"], 0), a["rain_rate_mm_hr"]), reverse=True)

    # Lead time for earliest critical alert
    earliest_lead_time = min((a["lead_time_minutes"] for a in active_alerts if a["lead_time_minutes"] > 0), default=0)

    return {
        "city": "Kolkata Metropolitan Area",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_alert_level": highest_alert,
        "earliest_lead_time_minutes": earliest_lead_time,
        "max_predicted_rain_rate_mm_hr": max_city_rain_rate,
        "active_alerts_count": len(active_alerts),
        "alerts": active_alerts,
        "zones_nowcast": zone_nowcasts,
    }
