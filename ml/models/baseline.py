def category(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def heuristic_predict(row: dict) -> float:
    return round(
        min(row["rainfall_24h"] / 220, 1) * 35
        + min(row["rainfall_7d"] / 650, 1) * 15
        + max(0, (20 - row["elevation"]) / 20) * 15
        + max(0, (100 - row["drainage_score"]) / 100) * 20
        + min(row["population_density"] / 32000, 1) * 10
        + min((row["historical_flood_count"] * 2 + row["citizen_report_count"] * 5) / 40, 1) * 5,
        1,
    )
