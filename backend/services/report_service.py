from sqlalchemy.orm import Session
from backend.database.models import CitizenReport
from backend.schemas.common import ReportCreate
from backend.services.geospatial_service import nearest_zone
from backend.services.risk_service import assess_zone


SEVERITY_WEIGHT = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def create_report(db: Session, payload: ReportCreate) -> dict:
    zone = nearest_zone(db, payload.latitude, payload.longitude)
    report = CitizenReport(zone_id=zone.id, **payload.model_dump())
    zone.citizen_report_count += max(1, SEVERITY_WEIGHT.get(payload.severity.upper(), 1))
    if payload.water_level_cm > 60:
        zone.citizen_report_count += 1
    before = zone.risk_score
    db.add(report)
    db.add(zone)
    db.commit()
    db.refresh(report)
    assessment = assess_zone(db, zone)
    alert = assessment["risk_score"] >= 76 and before < 76
    return {
        "report_id": report.id,
        "zone_id": zone.id,
        "zone_name": zone.name,
        "risk_before": before,
        "risk_after": assessment["risk_score"],
        "alert_generated": alert,
    }
