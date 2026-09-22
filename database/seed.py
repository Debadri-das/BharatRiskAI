import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.database.connection import get_supabase_admin_client
from backend.services.risk_service import refresh_all_risks


DEMO_ZONES = [
    {"name": "Zone 17 - Dhapa Wetlands", "latitude": 22.546, "longitude": 88.438, "rainfall_24h": 186, "rainfall_7d": 512, "elevation": 4.2, "drainage_score": 32, "population_density": 18500, "population": 41000, "historical_flood_count": 12, "area_km2": 3.1},
    {"name": "Zone 08 - Kalighat", "latitude": 22.522, "longitude": 88.343, "rainfall_24h": 154, "rainfall_7d": 448, "elevation": 8.5, "drainage_score": 42, "population_density": 23600, "population": 38500, "historical_flood_count": 8, "area_km2": 2.4},
    {"name": "Zone 04 - Salt Lake Sector V", "latitude": 22.575, "longitude": 88.433, "rainfall_24h": 138, "rainfall_7d": 390, "elevation": 6.8, "drainage_score": 51, "population_density": 17500, "population": 32000, "historical_flood_count": 6, "area_km2": 3.8},
    {"name": "Zone 12 - Howrah Maidan", "latitude": 22.589, "longitude": 88.31, "rainfall_24h": 168, "rainfall_7d": 470, "elevation": 5.5, "drainage_score": 38, "population_density": 28200, "population": 46000, "historical_flood_count": 10, "area_km2": 2.9},
    {"name": "Zone 21 - Behala", "latitude": 22.499, "longitude": 88.31, "rainfall_24h": 142, "rainfall_7d": 410, "elevation": 7.2, "drainage_score": 45, "population_density": 21400, "population": 39800, "historical_flood_count": 7, "area_km2": 4.2},
]


def main():
    client = get_supabase_admin_client()
    existing = client.table("zones").select("id").limit(1).execute().data
    if existing:
        print("Supabase already contains zone data; no seed rows inserted.")
        return
    client.table("zones").insert(DEMO_ZONES).execute()
    refresh_all_risks(client)
    print(f"Seeded {len(DEMO_ZONES)} Kolkata zones and refreshed their risk scores.")


if __name__ == "__main__":
    main()

