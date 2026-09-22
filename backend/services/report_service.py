from supabase import Client
from backend.schemas.common import ReportCreate
from backend.services.geospatial_service import nearest_zone
from backend.services.risk_service import assess_zone


SEVERITY_WEIGHT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def create_report(db: Client, payload: ReportCreate) -> dict:
    zone = nearest_zone(db, payload.latitude, payload.longitude)
    
    report_data = payload.model_dump()
    report_data["zone_id"] = zone["id"]
    
    # Update zone counts
    report_weight = max(1, SEVERITY_WEIGHT.get(payload.severity.upper(), 1))
    zone["citizen_report_count"] += report_weight
    if payload.water_level_cm > 60:
        zone["citizen_report_count"] += 1
        
    before = zone["risk_score"]
    
    # Insert report
    res = db.table("citizen_reports").insert(report_data).execute()
    report = res.data[0]
    
    assessment = assess_zone(db, zone, persist=True)
    db.table("zones").update({"citizen_report_count": zone["citizen_report_count"]}).eq("id", zone["id"]).execute()
    alert = assessment["risk_score"] >= 76 and before < 76
    return {
        "report_id": report["id"],
        "zone_id": zone["id"],
        "zone_name": zone["name"],
        "risk_before": before,
        "risk_after": assessment["risk_score"],
        "alert_generated": alert,
    }
