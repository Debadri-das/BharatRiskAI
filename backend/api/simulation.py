from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.schemas.common import SimulationRequest
from backend.services.simulation_service import run_simulation

router = APIRouter()


@router.post("/simulation")
def simulate(payload: SimulationRequest, db: Session = Depends(get_db)):
    return run_simulation(db, payload)
