"""
Meteorological & Spatiotemporal Feature Extraction for Severe Weather Nowcasting.
Extracts convective instability indices, radar proxies, moisture flux, and terrain parameters.
"""
from typing import Dict, Any, List

try:
    import numpy as np
except ImportError:
    np = None



NOWCAST_INTERVALS = ["2h", "3h", "4h", "5h", "6h"]

GRID_CHANNELS = [
    "iwv", "iwv_change", "ctt", "ctt_drop_rate", "qpe", "rainfall",
    "cape", "cin", "convergence", "wind_shear", "elevation", "slope", "drainage",
]

RAW_FEATURES = [
    "rainfall",      # mm/hr
    "rainfall_1h_accum",      # mm
    "rainfall_3h_accum",      # mm
    "radar_reflectivity_dbz", # dBZ proxy
    "cape",              # Convective Available Potential Energy (J/kg)
    "lifted_index",           # Stability (°C, negative = unstable)
    "dew_point_spread",       # Temp - Dew point (°C)
    "wind_speed_kmh",         # km/h
    "wind_gust_kmh",          # km/h
    "pressure_tendency_3h",   # hPa / 3h (e.g. -2.5 hPa drop)
    "elevation_m",            # meters
    "drainage_score",         # 0-100
]


def extract_features(data: Dict[str, Any]) -> List[float]:
    """Extract standard feature vector from observation or scenario dict."""
    # Scalar diagnostics (timeline/XAI) use the most recent grid cell only;
    # model tensors are built separately and retain every pixel and timestep.
    scalar_data = {}
    for key, value in data.items():
        if hasattr(value, "values"):
            value = value.values
        if np is not None and isinstance(value, np.ndarray) and value.ndim:
            value = float(value.reshape(-1)[-1])
        scalar_data[key] = value
    data = scalar_data
    vector = [
        float(data.get("rainfall_15m_rate", data.get("rainfall_24h", 0) / 8.0)),
        float(data.get("rainfall_1h_accum", data.get("rainfall_24h", 0) / 4.0)),
        float(data.get("rainfall_3h_accum", data.get("rainfall_24h", 0) / 2.0)),
        float(data.get("radar_reflectivity_dbz", min(65.0, max(10.0, float(data.get("rainfall_24h", 10)) * 0.25 + 15.0)))),
        # Updated to use unified feature schema
        float(data.get("cape", data.get("cape_j_kg", 1200.0))),
        float(data.get("lifted_index", -2.5)),

        float(data.get("dew_point_spread", 1.8)),
        float(data.get("wind_speed_kmh", 25.0)),
        float(data.get("wind_gust_kmh", 42.0)),
        float(data.get("pressure_tendency_3h", -1.8)),
        float(data.get("elevation_m", data.get("elevation", 6.0))),
        float(data.get("drainage_score", 45.0)),
        float(data.get("iwv", 45.0)),
        float(data.get("iwv_change", data.get("iwv_delta", 4.0))),
        float(data.get("ctt", -45.0)),
        float(data.get("ctt_drop_rate", 2.5)),
        float(data.get("qpe_mm_hr", data.get("qpe", 20.0))),
        float(data.get("cin_j_kg", -80.0)),
        float(data.get("low_level_convergence", 0.12)),
        float(data.get("wind_shear_ms", 12.0)),
        float(data.get("slope_degrees", 3.0)),
        float(data.get("rainfall", 24.0)),
        float(data.get("rainfall_1h_accum", data.get("rainfall_24h", 0) / 4.0)),
        float(data.get("rainfall_3h_accum", data.get("rainfall_24h", 0) / 2.0)),
        float(data.get("radar_reflectivity_dbz", min(65.0, max(10.0, float(data.get("rainfall_24h", 10)) * 0.25 + 15.0)))),
        float(data.get("elevation_m", data.get("elevation", 6.0))),
        float(data.get("drainage_score", 45.0)),
        
        float(data.get("cape", data.get("cape_j_kg", 1200.0))),
        float(data.get("lifted_index", -2.5)),
        float(data.get("dew_point_spread", 1.8)),
        float(data.get("wind_speed_kmh", 25.0)),
        float(data.get("wind_gust_kmh", 42.0)),
        float(data.get("pressure_tendency_3h", -1.8)),
        float(data.get("elevation_m", data.get("elevation", 6.0))),
        float(data.get("drainage_score", 45.0)),
    ]
    return vector


def build_spatiotemporal_features(
    observation: Dict[str, Any], time_steps: int = 7, grid_size: int = 16
) -> tuple["np.ndarray", "np.ndarray"]:
    """Create deterministic satellite/reanalysis-like grids for inference."""
    if np is None:
        raise RuntimeError("numpy is required to build nowcast tensors")
    
    # Validate sequence length
    if time_steps != 7:
        raise ValueError(f"Expected sequence length 7, got {time_steps}. Training and inference must use the same sequence length.")
    
    # Production callers pass arrays from the unified ingestion dataset.  Do
    # not collapse those arrays to means (or manufacture a spatial gradient).
    # A scalar mapping remains supported for small callers/tests, but is
    # explicitly broadcast and never used by the backend ingestion path.
    def as_grid(value: Any, name: str, temporal: bool) -> np.ndarray:
        if hasattr(value, "values"):
            value = value.values
        array = np.asarray(value, dtype=np.float32)
        if temporal:
            if array.ndim == 0:
                array = np.full((time_steps, grid_size, grid_size), array, dtype=np.float32)
            if array.ndim == 2:
                array = np.broadcast_to(array, (time_steps, *array.shape))
            if array.ndim != 3 or array.shape[0] != time_steps:
                raise ValueError(f"{name} must have shape [{time_steps}, height, width], got {array.shape}")
        else:
            if array.ndim == 3:
                if array.shape[0] != time_steps:
                    raise ValueError(f"{name} has invalid time dimension: {array.shape}")
                array = array[-1]
            if array.ndim == 0:
                array = np.full((grid_size, grid_size), array, dtype=np.float32)
            if array.ndim != 2:
                raise ValueError(f"{name} must be a 2-D grid, got {array.shape}")
        return array

    def channel(name: str, *aliases: str) -> np.ndarray:
        for key in (name, *aliases):
            if key in observation:
                return as_grid(observation[key], key, temporal=True)
        # Legacy scalar observations are retained for non-production utility
        # callers; real ingestion must provide every canonical channel.
        return as_grid(0.0, name, temporal=True)

    sequence = np.stack([channel(name) for name in GRID_CHANNELS], axis=1)
    height, width = sequence.shape[-2:]
    if (height, width) != (grid_size, grid_size):
        raise ValueError(f"Expected feature grid {grid_size}x{grid_size}, got {height}x{width}")
    baseline = np.stack([
        as_grid(observation.get("qpe", observation.get("qpe_mm_hr", 0.0)), "qpe", False),
        as_grid(observation.get("cin", observation.get("cin_j_kg", 0.0)), "cin", False),
        as_grid(observation.get("rainfall", 0.0), "rainfall", False),
        as_grid(observation.get("convergence", observation.get("low_level_convergence", 0.0)), "convergence", False),
        as_grid(observation.get("wind_shear", observation.get("wind_shear_ms", 0.0)), "wind_shear", False),
        as_grid(observation.get("elevation", observation.get("elevation_m", 0.0)), "elevation", False),
    ])
    return sequence.astype(np.float32), baseline.astype(np.float32)


def compute_convective_severity(features: Dict[str, float]) -> Dict[str, Any]:
    """Compute physical instability and severe weather probability indicators."""
    features = {
        key: (float(value.values.reshape(-1)[-1]) if hasattr(value, "values") else
              float(value.reshape(-1)[-1]) if np is not None and isinstance(value, np.ndarray) and value.ndim else value)
        for key, value in features.items()
    }
    cape = float(features.get("cape", features.get("cape_j_kg", 1200.0)))
    li = float(features.get("lifted_index", -2.0))
    dbz = float(features.get("radar_reflectivity_dbz", 35.0))
    rain_rate = float(features.get("rainfall_15m_rate", 20.0))
    gust = float(features.get("wind_gust_kmh", 35.0))
    cin = float(features.get("cin_j_kg", -80.0))
    convergence = float(features.get("low_level_convergence", 0.12))
    shear = float(features.get("wind_shear_ms", 12.0))
    iwv_change = float(features.get("iwv_change", features.get("iwv_delta", 4.0)))
    ctt_drop_rate = float(features.get("ctt_drop_rate", 2.5))
    
    # Severe thunderstorm probability (0 to 100%)
    instability_score = (min(cape / 3000.0, 1.0) * 0.28) + (max(0.0, min(-li / 6.0, 1.0)) * 0.22) + (min(dbz / 60.0, 1.0) * 0.2)
    instability_score += max(0.0, min(-cin / 150.0, 1.0)) * 0.1 + min(convergence / 0.3, 1.0) * 0.1
    instability_score += min(shear / 25.0, 1.0) * 0.05 + min(iwv_change / 15.0, 1.0) * 0.025 + min(ctt_drop_rate / 8.0, 1.0) * 0.025
    raw_prob = instability_score * 100.0
    thunderstorm_prob = round(max(5.0, min(98.0, raw_prob)), 1)

    
    # Lightning risk assessment
    if dbz >= 48.0 or cape >= 2200.0:
        lightning_risk = "SEVERE"
    elif dbz >= 40.0 or cape >= 1500.0:
        lightning_risk = "HIGH"
    elif dbz >= 30.0:
        lightning_risk = "MODERATE"
    else:
        lightning_risk = "LOW"
        
    # Squall / high wind risk
    squall_risk = "HIGH" if gust >= 60.0 or (cape >= 2000 and li <= -4) else ("MODERATE" if gust >= 45.0 else "LOW")

    return {
        "thunderstorm_prob": thunderstorm_prob,
        "lightning_risk": lightning_risk,
        "squall_risk": squall_risk,
        "is_cloudburst_threat": rain_rate >= 50.0 or (rain_rate >= 35.0 and dbz >= 52.0),
    }
