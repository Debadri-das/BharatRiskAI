from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from backend.database.connection import get_db
from backend.services.nowcast_service import get_citywide_nowcast, get_zone_nowcast
from backend.schemas.nowcast import CityNowcastOut, ZoneNowcastOut


router = APIRouter()


@router.get("/nowcast/city", response_model=CityNowcastOut)
def citywide_nowcast(live: bool = Query(True, description="Use decoded INSAT-3D and IMDAA products"), db: Client = Depends(get_db)):
    """Retrieve citywide 0-6h satellite-driven nowcasting."""
    return get_citywide_nowcast(db, live=live)


@router.get("/nowcast/zone/{zone_id}", response_model=ZoneNowcastOut)
def zone_nowcast(zone_id: int, live: bool = Query(True), db: Client = Depends(get_db)):
    """Retrieve hyper-local 0-6h nowcasting and convective trajectory for a single ward/zone."""
    nowcast = get_zone_nowcast(db, zone_id=zone_id, live=live)
    if not nowcast:
        raise HTTPException(status_code=404, detail="Zone not found")
    return nowcast


@router.get("/nowcast/alerts")
def nowcast_alerts(live: bool = Query(True), db: Client = Depends(get_db)):
    """Retrieve active early warning alerts prioritized by severity and lead time."""
    city_data = get_citywide_nowcast(db, live=live)
    return {
        "overall_alert_level": city_data["overall_alert_level"],
        "earliest_lead_time_minutes": city_data["earliest_lead_time_minutes"],
        "active_alerts_count": city_data["active_alerts_count"],
        "alerts": city_data["alerts"],
    }


