from ml.models.baseline import category, heuristic_predict


def test_baseline_prediction_returns_critical_for_extreme_case():
    score = heuristic_predict({
        "rainfall_24h": 210,
        "rainfall_7d": 620,
        "elevation": 3,
        "drainage_score": 25,
        "population_density": 30000,
        "historical_flood_count": 12,
        "citizen_report_count": 5,
    })
    assert score > 75
    assert category(score) == "CRITICAL"
