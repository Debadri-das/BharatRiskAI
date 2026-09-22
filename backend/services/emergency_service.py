from datetime import datetime
from supabase import Client
from backend.schemas.common import EmergencyCreate
import uuid

def calculate_priority(payload: EmergencyCreate) -> str:
    score = payload.people
    score += 8 if payload.emergency_type.upper() in {"TRAPPED", "MEDICAL", "DROWNING"} else 3
    score += len(payload.vulnerable) * 5
    if score >= 18:
        return "CRITICAL"
    if score >= 10:
        return "HIGH"
    return "MEDIUM"


def create_emergency(db: Client, payload: EmergencyCreate) -> dict:
    priority = calculate_priority(payload)
    message_id = payload.message_id or f"SOS-{uuid.uuid4().hex[:8].upper()}"
    
    # Check if duplicate message_id exists (e.g. multi-path mesh delivery)
    res = db.table("emergencies").select("*").eq("message_id", message_id).execute()
    if res.data:
        return emergency_payload(res.data[0])

    data = {
        "message_id": message_id,
        "emergency_type": payload.emergency_type.upper(),
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "people": payload.people,
        "vulnerable": ",".join(payload.vulnerable),
        "priority": priority,
        "status": "RECEIVED",
        "ttl": 10,
        "hop_count": 0,
    }
    
    insert_res = db.table("emergencies").insert(data).execute()
    return emergency_payload(insert_res.data[0])


def emergency_payload(emergency: dict) -> dict:
    return {
        "id": emergency["id"],
        "message_id": emergency["message_id"],
        "type": "EMERGENCY",
        "emergency_type": emergency["emergency_type"],
        "latitude": emergency["latitude"],
        "longitude": emergency["longitude"],
        "people": emergency["people"],
        "vulnerable": [v for v in emergency["vulnerable"].split(",") if v],
        "priority": emergency["priority"],
        "status": emergency["status"],
        "created_at": emergency["created_at"] or datetime.utcnow().isoformat(),
        "ttl": emergency["ttl"],
        "hop_count": emergency["hop_count"],
    }


def assign_resource(db: Client, emergency_id: int, resource_id: int) -> dict:
    emer_res = db.table("emergencies").select("*").eq("id", emergency_id).execute()
    res_res = db.table("resources").select("*").eq("id", resource_id).execute()
    
    if not emer_res.data or not res_res.data:
        raise ValueError("Emergency or resource not found")
        
    emergency = emer_res.data[0]
    resource = res_res.data[0]
    
    emergency["assigned_resource_id"] = resource["id"]
    emergency["status"] = "ASSIGNED"
    if resource["available"] > 0:
        db.table("resources").update({"available": resource["available"] - 1}).eq("id", resource["id"]).execute()
        
    update_res = db.table("emergencies").update({"assigned_resource_id": resource["id"], "status": "ASSIGNED"}).eq("id", emergency_id).execute()
    return emergency_payload(update_res.data[0])
