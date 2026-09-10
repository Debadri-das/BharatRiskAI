from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.connection import get_db
from backend.database.models import Zone
from ingestion.satellite import get_satellite_provider

router = APIRouter()


@router.get("/satellite/latest/{zone_id}")
def latest_satellite_scene(zone_id: int, live: bool = False, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    try:
        return get_satellite_provider(live=live).latest_scene(zone.latitude, zone.longitude)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/satellite/download/{zone_id}")
def download_satellite_scene(zone_id: int, live: bool = False, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    provider = get_satellite_provider(live=live)
    try:
        scene = provider.latest_scene(zone.latitude, zone.longitude)
        if not scene.get("available"):
            raise HTTPException(status_code=404, detail="No recent Sentinel-1 scene found")
        return provider.download_product(scene)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/satellite/process/{zone_id}")
def process_satellite_zone(zone_id: int, live: bool = False, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    try:
        return get_satellite_provider(live=live).process_zone(zone.latitude, zone.longitude)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error