from datetime import datetime
from fastapi import APIRouter, Depends
from supabase import Client
from backend.database.connection import get_db
from backend.services.recommendation_service import citywide_recommendations
from backend.services.risk_service import zone_payload

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Client = Depends(get_db)):
    zones = db.table("zones").select("*").order("risk_score", desc=True).execute().data
    emergencies = db.table("emergencies").select("*").order("created_at", desc=True).limit(5).execute().data
    reports = db.table("citizen_reports").select("*").order("created_at", desc=True).limit(5).execute().data
    queued_items = db.table("sync_queue").select("id", count="exact").eq("status", "PENDING").execute().count or 0
    
    overall = round(sum(z["risk_score"] for z in zones) / max(len(zones), 1), 1)
    
    return {
        "title": "BHARATRISK AI",
        "subtitle": "Disaster Intelligence & Emergency Response Platform",
        "status": "ONLINE",
        "updated_at": datetime.utcnow().isoformat(),
        "stats": {
            "overall_risk": overall,
            "critical_zones": len([z for z in zones if z["risk_category"] == "CRITICAL"]),
            "population_at_risk": sum(z["population"] for z in zones if z["risk_score"] >= 51),
            "active_alerts": len([z for z in zones if z["risk_score"] >= 76]),
            "pending_sos": len([e for e in emergencies if e["status"] != "ASSIGNED"]),
        },
        "zones": [zone_payload(zone) for zone in zones],
        "recommendations": citywide_recommendations(db),
        "reports": [
            {"id": r["id"], "zone_id": r["zone_id"], "severity": r["severity"], "water_level_cm": r["water_level_cm"], "description": r["description"], "created_at": r["created_at"]}
            for r in reports
        ],
        "emergencies": [
            {"id": e["id"], "message_id": e["message_id"], "emergency_type": e["emergency_type"], "people": e["people"], "priority": e["priority"], "status": e["status"], "created_at": e["created_at"]}
            for e in emergencies
        ],
        "risk_trend": [
            {"time": "06:00", "risk": max(30, overall - 18)},
            {"time": "09:00", "risk": max(35, overall - 11)},
            {"time": "12:00", "risk": overall},
            {"time": "15:00", "risk": min(100, overall + 8)},
            {"time": "18:00", "risk": min(100, overall + 13)},
        ],
        "queued_items": queued_items,
    }


@router.get("/connectivity")
def connectivity(db: Client = Depends(get_db)):
    queued_items = db.table("sync_queue").select("id", count="exact").eq("status", "PENDING").execute().count or 0
    return {
        "status": "ONLINE",
        "mesh_connected": True,
        "queued_items": queued_items,
        "checked_at": datetime.utcnow().isoformat(),
    }
