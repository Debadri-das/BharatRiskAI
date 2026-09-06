from sqlalchemy.orm import Session
from backend.database.models import Resource, Road, Shelter, Zone
from backend.services.risk_service import refresh_all_risks


ZONES = [
    ("Zone 17 - Dhapa Wetlands", 22.546, 88.438, 186, 512, 4.2, 32, 18500, 41000, 12, 3.1),
    ("Zone 08 - Kalighat", 22.522, 88.343, 154, 448, 8.5, 42, 23600, 38500, 8, 2.4),
    ("Zone 04 - Salt Lake Sector V", 22.575, 88.433, 138, 390, 6.8, 51, 17500, 32000, 6, 3.8),
    ("Zone 12 - Howrah Maidan", 22.589, 88.310, 168, 470, 5.5, 38, 28200, 46000, 10, 2.9),
    ("Zone 21 - Behala", 22.499, 88.310, 142, 410, 7.2, 45, 21400, 39800, 7, 4.2),
    ("Zone 02 - Esplanade", 22.567, 88.352, 126, 345, 10.5, 61, 30800, 27500, 5, 1.8),
    ("Zone 25 - Rajarhat", 22.623, 88.480, 118, 310, 9.8, 64, 12200, 24000, 3, 5.2),
    ("Zone 31 - Tollygunge", 22.496, 88.349, 132, 370, 11.0, 58, 19100, 30000, 4, 3.6),
]

RESOURCES = [
    ("NRS Medical Ambulance Unit", "ambulance", 22.565, 88.370, 8, 6, "OPEN"),
    ("KMC Pump Depot East", "water_pump", 22.552, 88.412, 9, 7, "OPEN"),
    ("NDRF Rescue Column A", "rescue_team", 22.570, 88.360, 5, 4, "OPEN"),
    ("River Patrol Boats", "boat", 22.586, 88.330, 7, 5, "PARTIAL"),
    ("Traffic Control Barricades", "road_closure", 22.560, 88.350, 20, 18, "OPEN"),
    ("Ward Emergency Personnel", "emergency_personnel", 22.548, 88.390, 30, 24, "OPEN"),
]

SHELTERS = [
    ("Community Hall Shelter - Park Circus", 22.542, 88.369, 900, 720),
    ("Salt Lake Stadium Relief Camp", 22.569, 88.409, 1800, 1400),
    ("Behala High School Shelter", 22.501, 88.319, 650, 510),
]


def seed_demo(db: Session) -> None:
    if db.query(Zone).count():
        refresh_all_risks(db)
        return
    for idx, row in enumerate(ZONES, start=1):
        db.add(
            Zone(
                id=idx,
                name=row[0],
                latitude=row[1],
                longitude=row[2],
                rainfall_24h=row[3],
                rainfall_7d=row[4],
                elevation=row[5],
                drainage_score=row[6],
                population_density=row[7],
                population=row[8],
                historical_flood_count=row[9],
                area_km2=row[10],
            )
        )
    for idx, row in enumerate(RESOURCES, start=1):
        db.add(Resource(id=idx, name=row[0], type=row[1], latitude=row[2], longitude=row[3], quantity=row[4], available=row[5], road_status=row[6]))
    for idx, row in enumerate(SHELTERS, start=1):
        db.add(Shelter(id=idx, name=row[0], latitude=row[1], longitude=row[2], capacity=row[3], available_capacity=row[4]))
    for idx, zone_id in enumerate([1, 2, 4, 5], start=1):
        db.add(Road(id=idx, name=["EM Bypass", "SP Mukherjee Road", "GT Road", "Diamond Harbour Road"][idx - 1], zone_id=zone_id, status="WATCH"))
    db.commit()
    refresh_all_risks(db)
