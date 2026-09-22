from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from backend.database.connection import get_db
from backend.database.crud import get_zone, list_zones
from backend.services.risk_service import zone_payload

router = APIRouter()


@router.get("/zones")
def zones(db: Client = Depends(get_db)):
    return [zone_payload(zone) for zone in list_zones(db)]


@router.get("/risk")
def risk(db: Client = Depends(get_db)):
    return [zone_payload(zone) for zone in list_zones(db)]


@router.get("/risk/{zone_id}")
def risk_detail(zone_id: int, db: Client = Depends(get_db)):
    zone = get_zone(db, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    return zone_payload(zone)
