from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from backend.database.connection import get_db
from backend.database.crud import get_zone, list_resources
from backend.services.recommendation_service import citywide_recommendations, recommendations_for_zone

router = APIRouter()


@router.get("/recommendations")
def recommendations(zone_id: int | None = None, db: Client = Depends(get_db)):
    if zone_id:
        zone = get_zone(db, zone_id)
        if not zone:
            raise HTTPException(404, "Zone not found")
        return recommendations_for_zone(db, zone)
    return citywide_recommendations(db)


@router.get("/resources")
def resources(db: Client = Depends(get_db)):
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item["type"],
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "quantity": item["quantity"],
            "available": item["available"],
            "road_status": item["road_status"],
        }
        for item in list_resources(db)
    ]
