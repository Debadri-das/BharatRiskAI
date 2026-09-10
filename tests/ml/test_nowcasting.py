from ml.nowcasting.features import extract_features, compute_convective_severity, NOWCAST_INTERVALS
from ml.nowcasting.model import WeatherNowcastModel


def test_convective_severity_calculation():
    severe_obs = {
        "rainfall_15m_rate": 55.0,
        "radar_reflectivity_dbz": 52.0,
        "cape_j_kg": 2400.0,
        "lifted_index": -5.5,
        "wind_gust_kmh": 68.0,
    }
    sev = compute_convective_severity(severe_obs)
    assert sev["thunderstorm_prob"] > 70.0
    assert sev["lightning_risk"] in ("HIGH", "SEVERE")
    assert sev["is_cloudburst_threat"] is True


def test_nowcast_timeline_generation():
    engine = WeatherNowcastModel()
    obs = {
        "rainfall_15m_rate": 45.0,
        "radar_reflectivity_dbz": 48.0,
        "cape_j_kg": 2100.0,
        "lifted_index": -4.0,
        "elevation": 4.5,
        "drainage_score": 35.0,
    }
    pred = engine.predict_nowcast(obs)
    assert pred["alert_level"] in ("ORANGE", "RED")
    assert len(pred["timeline"]) == len(NOWCAST_INTERVALS)
    assert pred["lead_time_minutes"] > 0
    assert pred["max_rain_rate_mm_hr"] > 0
