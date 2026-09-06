FEATURES = [
    "rainfall_24h",
    "rainfall_7d",
    "elevation",
    "drainage_score",
    "population_density",
    "historical_flood_count",
    "citizen_report_count",
]


def clean_frame(df):
    cleaned = df.copy()
    for column in FEATURES:
        cleaned[column] = cleaned[column].fillna(cleaned[column].median()).clip(lower=0)
    return cleaned
