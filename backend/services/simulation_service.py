from copy import copy
from supabase import Client
from backend.schemas.common import SimulationRequest
from backend.services.recommendation_service import recommendations_for_zone
from backend.services.risk_service import heuristic_score, risk_category, zone_payload


def run_simulation(db: Client, request: SimulationRequest) -> dict:
    q = db.table("zones").select("*")
    if request.zone_ids:
        q = q.in_("id", request.zone_ids)
    zones = q.execute().data
    
    results = []
    newly_critical = []
    population_newly_affected = 0
    affected_area = 0.0

    for zone in zones:
        simulated = zone.copy()
        simulated["rainfall_24h"] = max(0, zone["rainfall_24h"] * (1 + request.rainfall_percentage / 100))
        simulated["rainfall_7d"] = max(0, zone["rainfall_7d"] + simulated["rainfall_24h"] * request.duration_hours / 24 * 0.35)
        simulated["drainage_score"] = max(0, min(100, zone["drainage_score"] + request.drainage_efficiency_delta))
        simulated["elevation"] = max(0, zone["elevation"] + request.elevation_delta)
        
        simulated_score = heuristic_score(simulated)
        simulated_category = risk_category(simulated_score)
        
        if zone["risk_category"] != "CRITICAL" and simulated_category == "CRITICAL":
            newly_critical.append(zone["id"])
            population_newly_affected += zone["population"]
            affected_area += zone["area_km2"]
            
        results.append(
            {
                "zone": zone_payload(zone),
                "original_risk": zone["risk_score"],
                "simulated_risk": simulated_score,
                "difference": round(simulated_score - zone["risk_score"], 1),
                "simulated_category": simulated_category,
                "recommended_actions": recommendations_for_zone(db, simulated),
            }
        )

    return {
        "parameters": request.model_dump(),
        "zones": results,
        "newly_critical_zones": newly_critical,
        "population_newly_affected": population_newly_affected,
        "affected_area_km2": round(affected_area, 2),
    }
