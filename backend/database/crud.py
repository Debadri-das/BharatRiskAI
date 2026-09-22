from supabase import Client

def list_zones(db: Client):
    result = db.table("zones").select("*").order("risk_score", desc=True).execute()
    return result.data

def get_zone(db: Client, zone_id: int):
    result = db.table("zones").select("*").eq("id", zone_id).execute()
    return result.data[0] if result.data else None

def list_reports(db: Client, limit: int = 50):
    result = db.table("citizen_reports").select("*").order("created_at", desc=True).limit(limit).execute()
    return result.data

def list_emergencies(db: Client):
    result = db.table("emergencies").select("*").order("created_at", desc=True).execute()
    return result.data

def list_resources(db: Client):
    result = db.table("resources").select("*").order("type").order("name").execute()
    return result.data
