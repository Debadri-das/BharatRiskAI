from supabase import Client
from backend.utils.geo import nearest

def nearest_zone(db: Client, latitude: float, longitude: float) -> dict:
    res = db.table("zones").select("*").execute()
    zones = res.data
    return nearest(zones, latitude, longitude)
