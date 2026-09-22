from fastapi import APIRouter, Depends
from supabase import Client
from backend.database.connection import get_admin_db, get_db
from backend.database.crud import list_reports
from backend.schemas.common import ReportCreate
from backend.services.report_service import create_report

router = APIRouter()


@router.post("/report")
def submit_report(payload: ReportCreate, db: Client = Depends(get_admin_db)):
    return create_report(db, payload)


@router.get("/reports")
def reports(db: Client = Depends(get_db)):
    return [
        {
            "id": item["id"],
            "zone_id": item["zone_id"],
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "water_level_cm": item["water_level_cm"],
            "description": item["description"],
            "photo_url": item["photo_url"],
            "severity": item["severity"],
            "credible": item["credible"],
            "created_at": item["created_at"],
        }
        for item in list_reports(db)
    ]
