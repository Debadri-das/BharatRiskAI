"""Feature schemas and data cleaning for tabular flood hazard modeling."""
from __future__ import annotations

# Recommended feature schema for 2020 historical flood modeling experiments
HISTORICAL_FLOOD_FEATURES = [
    "rainfall_1h",           # INSAT QPE (mm)
    "rainfall_3h",           # INSAT QPE rolling 3h accumulation (mm)
    "rainfall_6h",           # INSAT QPE rolling 6h accumulation (mm)
    "rainfall_24h",          # 24-hour antecedent rainfall observations (mm)
    "rainfall_72h",          # 72-hour antecedent rainfall observations (mm)
    "elevation",             # Copernicus DEM elevation (m)
    "slope",                 # Topographic slope (degrees)
    "flow_accumulation",     # Hydrologically conditioned flow accumulation (cells)
    "drainage_proximity",    # Terrain/hydrological drainage distance/score
    "soil_moisture",         # IMDAA reanalysis soil moisture (if available)
    "river_proximity",       # Distance to active river channels/drainage lines (m)
    "population_density",    # Static exposure feature (people/km2)
]

# Detailed metadata documenting authoritative sources for each feature
FEATURE_SOURCES = {
    "rainfall_1h": "INSAT QPE instantaneous rate / 1h accumulation",
    "rainfall_3h": "INSAT QPE rolling 3-hour accumulation (sum_{i=1}^6 r_i Delta t_i)",
    "rainfall_6h": "INSAT QPE rolling 6-hour accumulation (sum_{i=1}^{12} r_i Delta t_i)",
    "rainfall_24h": "Historical rainfall observations (24h accumulation)",
    "rainfall_72h": "Historical rainfall observations (72h antecedent saturation)",
    "elevation": "Copernicus DEM GLO-30 elevation (m)",
    "slope": "Topographic slope derived from Copernicus DEM (degrees)",
    "flow_accumulation": "Hydrological preprocessing (D8 priority-flood routing)",
    "drainage_proximity": "Derived terrain and hydrological drainage pathways",
    "soil_moisture": "NCMRWF IMDAA reanalysis soil moisture (surface/root-zone)",
    "river_proximity": "GIS hydrological network distance (m)",
    "population_density": "Static census / gridded population exposure (people/km2)",
}

# Features that can introduce data leakage unless verified point-in-time
LEAKAGE_PRONE_FEATURES = {
    "historical_flood_count": (
        "PROHIBITED unless strict point-in-time timestamps and event provenance "
        "confirm that counts reflect only confirmed flood events strictly before prediction issue_time."
    ),
    "citizen_report_count": (
        "PROHIBITED unless verified that reports were timestamped and received strictly "
        "before prediction issue_time. Static or post-event aggregations cause severe leakage."
    ),
}

# Legacy demo schema retained for reference and heuristic baseline compatibility
LEGACY_DEMO_FEATURES = [
    "rainfall_24h",
    "rainfall_7d",
    "elevation",
    "drainage_score",
    "population_density",
    "historical_flood_count",
    "citizen_report_count",
]

# Active standard schema defaults to the 2020 historical experiment specification
FEATURES = HISTORICAL_FLOOD_FEATURES


def clean_frame(df, features=None):
    """Normalize infinities without inventing values.

    Imputation is performed by the estimator pipeline after the temporal
    split, so validation and training retain missingness information.
    """
    cleaned = df.copy()
    feature_columns = (
        features
        if features is not None
        else [col for col in cleaned.columns if col in set(HISTORICAL_FLOOD_FEATURES) | set(LEGACY_DEMO_FEATURES)]
    )
    for column in feature_columns:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].replace([float("inf"), -float("inf")], float("nan"))
    return cleaned
