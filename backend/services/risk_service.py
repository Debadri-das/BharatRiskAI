from __future__ import annotations

from sqlalchemy.orm import Session
from backend.database.models import RiskAssessment, Zone


def risk_category(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def contribution_breakdown(zone: Zone) -> dict[str, float]:
    raw = {
        "rainfall": min(zone.rainfall_24h / 220, 1) * 35,
        "weekly_saturation": min(zone.rainfall_7d / 650, 1) * 15,
        "low_elevation": max(0, (20 - zone.elevation) / 20) * 15,
        "poor_drainage": max(0, (100 - zone.drainage_score) / 100) * 20,
        "population_exposure": min(zone.population_density / 32000, 1) * 10,
        "history_and_reports": min((zone.historical_flood_count * 2 + zone.citizen_report_count * 5) / 40, 1) * 5,
    }
    total = sum(raw.values()) or 1
    return {key: round(value * 100 / total, 1) for key, value in raw.items()}


def heuristic_score(zone: Zone) -> float:
    score = (
        min(zone.rainfall_24h / 220, 1) * 35
        + min(zone.rainfall_7d / 650, 1) * 15
        + max(0, (20 - zone.elevation) / 20) * 15
        + max(0, (100 - zone.drainage_score) / 100) * 20
        + min(zone.population_density / 32000, 1) * 10
        + min((zone.historical_flood_count * 2 + zone.citizen_report_count * 5) / 40, 1) * 5
    )
    return round(max(0, min(100, score)), 1)


try:
    from ml.models.model_loader import FloodRiskModel
    _flood_model = FloodRiskModel()
except Exception:
    _flood_model = None


def calculate_zone_score(zone: Zone) -> tuple[float, str, float]:
    """Calculate risk score, category and confidence using ML model with heuristic fallback."""
    if _flood_model is not None:
        try:
            pred = _flood_model.predict({
                "rainfall_24h": zone.rainfall_24h,
                "rainfall_7d": zone.rainfall_7d,
                "elevation": zone.elevation,
                "drainage_score": zone.drainage_score,
                "population_density": zone.population_density,
                "historical_flood_count": zone.historical_flood_count,
                "citizen_report_count": zone.citizen_report_count,
            })
            return pred["risk_score"], pred["risk_category"], pred["confidence"]
        except Exception:
            pass
    score = heuristic_score(zone)
    category = risk_category(score)
    confidence = 0.82 if zone.citizen_report_count else 0.76
    return score, category, confidence


def assess_zone(db: Session, zone: Zone, persist: bool = True) -> dict:
    score, category, confidence = calculate_zone_score(zone)
    zone.risk_score = score
    zone.risk_category = category
    if persist:
        db.add(RiskAssessment(zone_id=zone.id, score=score, category=category, confidence=confidence))
        db.add(zone)
        db.commit()
        db.refresh(zone)
    return {"risk_score": score, "risk_category": category, "confidence": confidence}



def zone_payload(zone: Zone) -> dict:
    return {
        "id": zone.id,
        "name": zone.name,
        "latitude": zone.latitude,
        "longitude": zone.longitude,
        "rainfall_24h": zone.rainfall_24h,
        "rainfall_7d": zone.rainfall_7d,
        "elevation": zone.elevation,
        "drainage_score": zone.drainage_score,
        "population_density": zone.population_density,
        "population": zone.population,
        "historical_flood_count": zone.historical_flood_count,
        "citizen_report_count": zone.citizen_report_count,
        "risk_score": zone.risk_score,
        "risk_category": zone.risk_category,
        "area_km2": zone.area_km2,
        "breakdown": contribution_breakdown(zone),
    }


def refresh_all_risks(db: Session) -> None:
    for zone in db.query(Zone).all():
        assess_zone(db, zone, persist=False)
    db.commit()
