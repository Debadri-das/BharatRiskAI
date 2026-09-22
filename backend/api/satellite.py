from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from backend.database.connection import get_db
from backend.database.crud import get_zone
from ingestion.satellite import get_satellite_provider

router = APIRouter()


@router.get("/satellite/latest/{zone_id}")
def latest_satellite_scene(zone_id: int, live: bool = False, db: Client = Depends(get_db)):
    zone = get_zone(db, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    try:
        return get_satellite_provider(live=live).latest_scene(zone["latitude"], zone["longitude"])
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/satellite/download/{zone_id}")
def download_satellite_scene(zone_id: int, live: bool = False, db: Client = Depends(get_db)):
    zone = get_zone(db, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    provider = get_satellite_provider(live=live)
    try:
        scene = provider.latest_scene(zone["latitude"], zone["longitude"])
        if not scene.get("available"):
            raise HTTPException(status_code=404, detail="No recent Sentinel-1 scene found")
        return provider.download_product(scene)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/satellite/process/{zone_id}")
def process_satellite_zone(zone_id: int, live: bool = False, db: Client = Depends(get_db)):
    zone = get_zone(db, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    try:
        return get_satellite_provider(live=live).process_zone(zone["latitude"], zone["longitude"])
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error