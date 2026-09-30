from backend.services.nowcast_service import build_probability_layers, validate_nowcast_output
from worker.tasks.risk_update import update_risk
from worker.tasks.alert_processing import process_alerts


def ready_prediction():
    return {
        "status": "READY",
        "alert_level": "ORANGE",
        "primary_hazard": "HEAVY RAIN",
        "timeline": [{"interval": "2h"}],
        "hazard_probability_maps": {"thunderstorms": [[[0.4]]]}
    }


def test_consumers_block_without_model_outputs():
    assert update_risk()["status"] == "BLOCKED"
    assert process_alerts()["status"] == "BLOCKED"


def test_model_output_is_validated_and_keeps_geospatial_extent():
    prediction = ready_prediction()
    assert validate_nowcast_output(prediction) is None
    layer = build_probability_layers(prediction["hazard_probability_maps"], [88.2, 22.4, 88.4, 22.6], [2])[0]
    assert layer["type"] == "raster"
    assert layer["horizon_hours"] == 2
    assert layer["bounds"]["west"] == 88.2


def test_risk_update_rejects_incomplete_output():
    result = update_risk([{"status": "READY"}])
    assert result["status"] == "BLOCKED"
    assert "missing" in result["blocked_reason"]
