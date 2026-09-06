from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models import Emergency, Resource
from backend.schemas.common import EmergencyCreate


def calculate_priority(payload: EmergencyCreate) -> str:
    score = payload.people
    score += 8 if payload.emergency_type.upper() in {"TRAPPED", "MEDICAL", "DROWNING"} else 3
    score += len(payload.vulnerable) * 5
    if score >= 18:
        return "CRITICAL"
    if score >= 10:
        return "HIGH"
    return "MEDIUM"


def create_emergency(db: Session, payload: EmergencyCreate) -> dict:
    priority = calculate_priority(payload)
    next_id = db.query(Emergency).count() + 1
    emergency = Emergency(
        message_id=f"SOS-{next_id:03d}",
        emergency_type=payload.emergency_type.upper(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        people=payload.people,
        vulnerable=",".join(payload.vulnerable),
        priority=priority,
        status="RECEIVED",
        ttl=10,
        hop_count=0,
    )
    db.add(emergency)
    db.commit()
    db.refresh(emergency)
    return emergency_payload(emergency)


def emergency_payload(emergency: Emergency) -> dict:
    return {
        "id": emergency.id,
        "message_id": emergency.message_id,
        "type": "EMERGENCY",
        "emergency_type": emergency.emergency_type,
        "latitude": emergency.latitude,
        "longitude": emergency.longitude,
        "people": emergency.people,
        "vulnerable": [v for v in emergency.vulnerable.split(",") if v],
        "priority": emergency.priority,
        "status": emergency.status,
        "created_at": emergency.created_at or datetime.utcnow(),
        "ttl": emergency.ttl,
        "hop_count": emergency.hop_count,
    }


def assign_resource(db: Session, emergency_id: int, resource_id: int) -> dict:
    emergency = db.get(Emergency, emergency_id)
    resource = db.get(Resource, resource_id)
    if not emergency or not resource:
        raise ValueError("Emergency or resource not found")
    emergency.assigned_resource_id = resource.id
    emergency.status = "ASSIGNED"
    if resource.available > 0:
        resource.available -= 1
    db.commit()
    db.refresh(emergency)
    return emergency_payload(emergency)
