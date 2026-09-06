from sqlalchemy.orm import Session
from backend.database.models import CitizenReport, Emergency, Resource, Zone


def list_zones(db: Session):
    return db.query(Zone).order_by(Zone.risk_score.desc()).all()


def get_zone(db: Session, zone_id: int):
    return db.get(Zone, zone_id)


def list_reports(db: Session, limit: int = 50):
    return db.query(CitizenReport).order_by(CitizenReport.created_at.desc()).limit(limit).all()


def list_emergencies(db: Session):
    return db.query(Emergency).order_by(Emergency.created_at.desc()).all()


def list_resources(db: Session):
    return db.query(Resource).order_by(Resource.type, Resource.name).all()
