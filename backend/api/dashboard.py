from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import CitizenReport, Emergency, SyncQueue, Zone
from backend.services.recommendation_service import citywide_recommendations
from backend.services.risk_service import zone_payload

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    zones = db.query(Zone).order_by(Zone.risk_score.desc()).all()
    emergencies = db.query(Emergency).order_by(Emergency.created_at.desc()).limit(5).all()
    reports = db.query(CitizenReport).order_by(CitizenReport.created_at.desc()).limit(5).all()
    overall = round(sum(z.risk_score for z in zones) / max(len(zones), 1), 1)
    return {
        "title": "BHARATRISK AI",
        "subtitle": "Disaster Intelligence & Emergency Response Platform",
        "status": "ONLINE",
        "updated_at": datetime.utcnow(),
        "stats": {
            "overall_risk": overall,
            "critical_zones": len([z for z in zones if z.risk_category == "CRITICAL"]),
            "population_at_risk": sum(z.population for z in zones if z.risk_score >= 51),
            "active_alerts": len([z for z in zones if z.risk_score >= 76]),
            "pending_sos": len([e for e in emergencies if e.status != "ASSIGNED"]),
        },
        "zones": [zone_payload(zone) for zone in zones],
        "recommendations": citywide_recommendations(db),
        "reports": [
            {"id": r.id, "zone_id": r.zone_id, "severity": r.severity, "water_level_cm": r.water_level_cm, "description": r.description, "created_at": r.created_at}
            for r in reports
        ],
        "emergencies": [
            {"id": e.id, "message_id": e.message_id, "emergency_type": e.emergency_type, "people": e.people, "priority": e.priority, "status": e.status, "created_at": e.created_at}
            for e in emergencies
        ],
        "risk_trend": [
            {"time": "06:00", "risk": max(30, overall - 18)},
            {"time": "09:00", "risk": max(35, overall - 11)},
            {"time": "12:00", "risk": overall},
            {"time": "15:00", "risk": min(100, overall + 8)},
            {"time": "18:00", "risk": min(100, overall + 13)},
        ],
        "queued_items": db.query(SyncQueue).filter(SyncQueue.status == "PENDING").count(),
    }


@router.get("/connectivity")
def connectivity(db: Session = Depends(get_db)):
    return {
        "status": "ONLINE",
        "mesh_connected": True,
        "queued_items": db.query(SyncQueue).filter(SyncQueue.status == "PENDING").count(),
        "checked_at": datetime.utcnow(),
    }
