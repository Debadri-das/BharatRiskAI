from datetime import datetime
from pydantic import BaseModel, Field


class ZoneOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    rainfall_24h: float
    rainfall_7d: float
    elevation: float
    drainage_score: float
    population_density: float
    population: int
    historical_flood_count: int
    citizen_report_count: int
    risk_score: float
    risk_category: str
    area_km2: float
    breakdown: dict[str, float] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ReportCreate(BaseModel):
    latitude: float
    longitude: float
    water_level_cm: float = Field(ge=0, le=500)
    description: str = Field(min_length=3, max_length=1000)
    photo_url: str | None = None
    severity: str = "MEDIUM"


class EmergencyCreate(BaseModel):
    emergency_type: str
    latitude: float
    longitude: float
    people: int = Field(ge=1, le=500)
    vulnerable: list[str] = Field(default_factory=list)
    description: str | None = None


class SimulationRequest(BaseModel):
    rainfall_percentage: float = 0
    drainage_efficiency_delta: float = 0
    duration_hours: int = Field(default=24, ge=1, le=168)
    elevation_delta: float = 0
    zone_ids: list[int] | None = None


class AssignRequest(BaseModel):
    resource_id: int


class ConnectivityOut(BaseModel):
    status: str
    mesh_connected: bool
    queued_items: int
    checked_at: datetime
