from sqlalchemy.orm import Session
from backend.database.models import Zone
from backend.utils.geo import nearest


def nearest_zone(db: Session, latitude: float, longitude: float) -> Zone:
    zones = db.query(Zone).all()
    return nearest(zones, latitude, longitude)
