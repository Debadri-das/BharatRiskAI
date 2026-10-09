"""
Nowcasting & Early Warning Service.
Integrates live weather observation ingestion, convective instability models,
and generates hyper-local 0-6h predictions, alert levels, and lead times.
"""
from typing import Dict, Any, List, Optional
import os
import numpy as np
from datetime import datetime, timezone
from supabase import Client

from ingestion.pipeline import UnifiedFeaturePipeline
from ml.nowcasting.model import WeatherNowcastModel


_nowcast_engine = WeatherNowcastModel()
_checkpoint = os.getenv("NOWCAST_CHECKPOINT")
_normalization = os.getenv("NOWCAST_NORMALIZATION")
if _checkpoint and os.path.exists(_checkpoint):
    _nowcast_engine.load_artifact(_checkpoint)
if _normalization and os.path.exists(_normalization):
    _nowcast_engine.load_normalization(_normalization)


def reload_nowcast_engine(checkpoint_path: Optional[str] = None, normalization_path: Optional[str] = None) -> WeatherNowcastModel:
    """Reload the nowcasting engine weights and normalization statistics."""
    global _nowcast_engine
    ckpt = checkpoint_path or os.getenv("NOWCAST_CHECKPOINT")
    norm = normalization_path or os.getenv("NOWCAST_NORMALIZATION")
    if ckpt and os.path.exists(ckpt):
        _nowcast_engine.load_artifact(ckpt)
    if norm and os.path.exists(norm):
        _nowcast_engine.load_normalization(norm)
    return _nowcast_engine


def get_zone_nowcast(db: Client, zone_id: int, live: bool = True) -> Optional[Dict[str, Any]]:
    """Generate hyper-local 0-6h severe weather nowcast for a specific zone."""
    res = db.table("zones").select("*").eq("id", zone_id).execute()
    if not res.data:
        return None
    zone = res.data[0]

    # Extract features using the unified feature pipeline
    bbox = [zone["longitude"] - 0.1, zone["latitude"] - 0.1, zone["longitude"] + 0.1, zone["latitude"] + 0.1]
    start_time = datetime.now(timezone.utc)
    end_time = start_time
    
    pipeline = UnifiedFeaturePipeline(bbox, start_time, end_time)
    features = pipeline.extract_features()
    
    # Preserve the temporal/spatial tensors.  Reducing these to scalar means
    # destroys storm structure and makes the multitask model ineffective.
    obs = {channel: features[channel].values for channel in features.data_vars}
    
    # Merge zone physical parameters
    # Zone metadata is not a model grid; only use it for API context and for
    # legacy scalar diagnostic calculations where a canonical grid is absent.
    obs["population"] = zone["population"]


    try:
        prediction = _nowcast_engine.predict_nowcast(obs)
        validation_error = validate_nowcast_output(prediction)
    except Exception as error:
        prediction = None
        validation_error = f"nowcast inference failed: {error}"

    if validation_error:
        return _zone_status(zone, "BLOCKED", validation_error)

    prediction["status"] = "READY"
    # Calibration is deliberately explicit.  The current inference contract
    # does not supply a calibration artifact, so downstream code must not call
    # these values calibrated unless a future model does so.
    prediction.setdefault("calibration_status", "UNSPECIFIED")
    prediction["probability_layers"] = build_probability_layers(
        prediction["hazard_probability_maps"], bbox, prediction.get("forecast_horizons_hours")
    )

    def latest_value(name: str):
        value = obs.get(name)
        if value is None:
            return None
        array = np.asarray(value)
        return float(array.reshape(-1)[-1])

    return {
        "zone_id": zone["id"],
        "zone_name": zone["name"],
        "latitude": zone["latitude"],
        "longitude": zone["longitude"],
        "current_weather": {
            "rainfall_15m_rate": latest_value("rainfall"),
            "temperature_c": latest_value("temperature_c"),
            "humidity_percent": latest_value("humidity_percent"),
            "wind_speed_kmh": latest_value("wind_speed_kmh"),
            "radar_reflectivity_dbz": latest_value("radar_reflectivity_dbz"),
            "cape_j_kg": latest_value("cape"),
        },
        "nowcast": prediction,
        "status": "READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_nowcast_output(output: Optional[Dict[str, Any]]) -> Optional[str]:
    """Validate the minimum model contract before alert/risk consumers use it."""
    if not isinstance(output, dict):
        return "missing nowcast output"
    required = ("alert_level", "primary_hazard", "timeline", "hazard_probability_maps")
    missing = [key for key in required if key not in output]
    if missing:
        return f"nowcast output missing required fields: {', '.join(missing)}"
    if output.get("status") == "BLOCKED":
        return output.get("blocked_reason") or "nowcast output is blocked"
    if not output["timeline"] or not isinstance(output["hazard_probability_maps"], dict):
        return "nowcast output has no usable forecast data"
    return None


def build_probability_layers(maps: Dict[str, Any], bounds: List[float], horizons: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """Describe model grids as geographic raster layers without changing values."""
    layers = []
    for hazard, horizon_values in maps.items():
        for index, values in enumerate(horizon_values):
            rows = len(values)
            columns = len(values[0]) if rows else 0
            layers.append({
                "id": f"{hazard}-{index}", "hazard": hazard, "horizon_index": index,
                "horizon_hours": (horizons[index] if horizons and index < len(horizons) else None),
                "type": "raster", "crs": "EPSG:4326",
                "bounds": {"west": bounds[0], "south": bounds[1], "east": bounds[2], "north": bounds[3]},
                "width": columns, "height": rows, "values": values,
            })
    return layers


def _zone_status(zone: Dict[str, Any], status: str, reason: str) -> Dict[str, Any]:
    return {
        "zone_id": zone["id"], "zone_name": zone["name"],
        "latitude": zone["latitude"], "longitude": zone["longitude"],
        "current_weather": {}, "nowcast": None, "status": status,
        "blocked_reason": reason, "generated_at": datetime.now(timezone.utc).isoformat(),
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
        if zn.get("status") != "READY" or not zn.get("nowcast"):
            continue
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
        "status": "READY" if any(z.get("status") == "READY" for z in zone_nowcasts) else "BLOCKED",
        "blocked_zones": [
            {"zone_id": z["zone_id"], "reason": z.get("blocked_reason", "not ready")}
            for z in zone_nowcasts if z.get("status") != "READY"
        ],
    }
