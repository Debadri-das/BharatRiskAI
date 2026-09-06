from backend.services.risk_service import risk_category
from backend.schemas.common import EmergencyCreate
from backend.services.emergency_service import calculate_priority


def test_risk_categories():
    assert risk_category(20) == "LOW"
    assert risk_category(49) == "MEDIUM"
    assert risk_category(70) == "HIGH"
    assert risk_category(90) == "CRITICAL"


def test_emergency_priority_with_vulnerable_people():
    payload = EmergencyCreate(emergency_type="TRAPPED", latitude=22.5, longitude=88.3, people=4, vulnerable=["elderly", "child"])
    assert calculate_priority(payload) == "CRITICAL"
