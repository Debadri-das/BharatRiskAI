from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class NowcastIntervalOut(BaseModel):
    interval: str
    rain_rate_mm_hr: float
    radar_dbz: float
    wind_gust_kmh: float
    flood_threat_score: float
    thunderstorm_prob: float
    confidence: float


class NowcastPredictionOut(BaseModel):
    alert_level: str
    primary_hazard: str
    lead_time_minutes: int
    peak_interval: str
    max_rain_rate_mm_hr: float
    max_flood_threat_score: float
    thunderstorm_prob: float
    lightning_risk: str
    squall_risk: str
    advisory: str
    timeline: List[NowcastIntervalOut]


class ZoneNowcastOut(BaseModel):
    zone_id: int
    zone_name: str
    latitude: float
    longitude: float
    current_weather: Dict[str, Any]
    nowcast: NowcastPredictionOut
    generated_at: str


class EarlyWarningAlertOut(BaseModel):
    zone_id: int
    zone_name: str
    alert_level: str
    primary_hazard: str
    lead_time_minutes: int
    peak_interval: str
    rain_rate_mm_hr: float
    advisory: str


class CityNowcastOut(BaseModel):
    city: str
    generated_at: str
    overall_alert_level: str
    earliest_lead_time_minutes: int
    max_predicted_rain_rate_mm_hr: float
    active_alerts_count: int
    alerts: List[EarlyWarningAlertOut]
    zones_nowcast: List[ZoneNowcastOut]


class NowcastSimulationRequest(BaseModel):
    cloudburst_intensity: float = Field(default=1.0, ge=0.0, le=3.0, description="Multiplier for cloudburst downpour")
    convective_cape: float = Field(default=1800.0, ge=200.0, le=4000.0, description="Convective Available Potential Energy (J/kg)")
    radar_dbz_boost: float = Field(default=0.0, ge=-20.0, le=30.0, description="Radar reflectivity modifier")
    storm_speed_kmh: float = Field(default=25.0, ge=5.0, le=80.0, description="Storm movement velocity")
    zone_ids: Optional[List[int]] = None
