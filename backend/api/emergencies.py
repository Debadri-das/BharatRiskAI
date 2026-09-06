from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.crud import list_emergencies
from backend.schemas.common import AssignRequest, EmergencyCreate
from backend.services.emergency_service import assign_resource, create_emergency, emergency_payload

router = APIRouter()


@router.post("/emergency")
def emergency(payload: EmergencyCreate, db: Session = Depends(get_db)):
    return create_emergency(db, payload)


@router.get("/emergencies")
def emergencies(db: Session = Depends(get_db)):
    return [emergency_payload(item) for item in list_emergencies(db)]


@router.post("/emergency/{emergency_id}/assign")
def assign(emergency_id: int, payload: AssignRequest, db: Session = Depends(get_db)):
    try:
        return assign_resource(db, emergency_id, payload.resource_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
