from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from supabase import Client

from backend.database.connection import get_db
from backend.database.crud import list_zones
from backend.services.nowcast_service import get_citywide_nowcast, get_zone_nowcast
from backend.schemas.nowcast import CityNowcastOut, ZoneNowcastOut, NowcastSimulationRequest
from ml.nowcasting.model import WeatherNowcastModel


router = APIRouter()
_sim_engine = WeatherNowcastModel()


@router.get("/nowcast/city", response_model=CityNowcastOut)
def citywide_nowcast(live: bool = Query(False, description="Fetch live weather from Open-Meteo"), db: Client = Depends(get_db)):
    """Retrieve citywide 0-6h severe weather nowcasting with early warnings and lead times."""
    return get_citywide_nowcast(db, live=live)


@router.get("/nowcast/zone/{zone_id}", response_model=ZoneNowcastOut)
def zone_nowcast(zone_id: int, live: bool = Query(False), db: Client = Depends(get_db)):
    """Retrieve hyper-local 0-6h nowcasting and convective trajectory for a single ward/zone."""
    nowcast = get_zone_nowcast(db, zone_id=zone_id, live=live)
    if not nowcast:
        raise HTTPException(status_code=404, detail="Zone not found")
    return nowcast


@router.get("/nowcast/alerts")
def nowcast_alerts(live: bool = Query(False), db: Client = Depends(get_db)):
    """Retrieve active early warning alerts prioritized by severity and lead time."""
    city_data = get_citywide_nowcast(db, live=live)
    return {
        "overall_alert_level": city_data["overall_alert_level"],
        "earliest_lead_time_minutes": city_data["earliest_lead_time_minutes"],
        "active_alerts_count": city_data["active_alerts_count"],
        "alerts": city_data["alerts"],
    }


@router.post("/nowcast/simulate")
def simulate_nowcast_storm(payload: NowcastSimulationRequest, db: Client = Depends(get_db)):
    """Simulate severe weather progression under adjusted cloudburst, CAPE, and radar parameters."""
    zones = list_zones(db)
    if payload.zone_ids:
        zones = [zone for zone in zones if zone["id"] in payload.zone_ids]

    sim_results = []
    new_critical = []
    
    for zone in zones:
        sim_obs = {
            "rainfall_15m_rate": round(35.0 * payload.cloudburst_intensity, 1),
            "rainfall_1h_accum": round(45.0 * payload.cloudburst_intensity, 1),
            "rainfall_3h_accum": round(90.0 * payload.cloudburst_intensity, 1),
            "rainfall_24h": round(zone["rainfall_24h"] * payload.cloudburst_intensity, 1),
            "radar_reflectivity_dbz": round(min(65.0, 38.0 + payload.radar_dbz_boost + 15.0 * payload.cloudburst_intensity), 1),
            "cape_j_kg": payload.convective_cape,
            "lifted_index": -1.5 - (payload.convective_cape / 500.0),
            "wind_speed_kmh": payload.storm_speed_kmh,
            "wind_gust_kmh": payload.storm_speed_kmh * 1.8,
            "elevation": zone["elevation"],
            "drainage_score": zone["drainage_score"],
            "population": zone["population"],
        }
        pred = _sim_engine.predict_nowcast(sim_obs)
        if pred["alert_level"] in ("RED", "ORANGE"):
            new_critical.append(zone["id"])
            
        sim_results.append({
            "zone_id": zone["id"],
            "zone_name": zone["name"],
            "simulated_nowcast": pred,
        })

    return {
        "parameters": payload.model_dump(),
        "simulated_zones": sim_results,
        "high_risk_zones_count": len(new_critical),
        "high_risk_zone_ids": new_critical,
    }
