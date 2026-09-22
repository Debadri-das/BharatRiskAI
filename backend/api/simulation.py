from fastapi import APIRouter, Depends
from supabase import Client
from backend.database.connection import get_db
from backend.schemas.common import SimulationRequest
from backend.services.simulation_service import run_simulation

router = APIRouter()


@router.post("/simulation")
def simulate(payload: SimulationRequest, db: Client = Depends(get_db)):
    return run_simulation(db, payload)
