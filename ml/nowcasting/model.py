"""PyTorch-backed severe-weather nowcasting facade."""

from typing import Any, Dict

import numpy as np
import torch

from ml.nowcasting.architecture import SpatiotemporalMTLNet
from ml.nowcasting.features import (
    NOWCAST_INTERVALS,
    build_spatiotemporal_features,
    compute_convective_severity,
    extract_features,
)


class WeatherNowcastModel:
    def __init__(self, device: str = "cpu") -> None:
        self.device = torch.device(device)
        self.model = SpatiotemporalMTLNet().to(self.device)
        self.model.eval()

    @torch.inference_mode()
    def predict_grid(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        sequence, baseline = build_spatiotemporal_features(observation)
        outputs = self.model(
            torch.from_numpy(sequence).unsqueeze(0).to(self.device, dtype=torch.float32),
            torch.from_numpy(baseline).unsqueeze(0).to(self.device, dtype=torch.float32),
        )
        return {
            name: tensor.squeeze(0).cpu().numpy().round(4).tolist()
            for name, tensor in outputs.items()
        }

    def predict_nowcast(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        feats = extract_features(observation)
        convective = compute_convective_severity(observation)
        grids = self.predict_grid(observation)
        hazards = {name: float(np.max(values) * 100.0) for name, values in grids.items()}
        base_rain_rate, radar_dbz = feats[0], feats[3]
        wind_gust, elevation, drainage = feats[8], feats[10], feats[11]
        multipliers = {"2h": 1.20, "3h": 0.95, "4h": 0.72, "5h": 0.52, "6h": 0.35}
        timeline = []
        max_rain_rate, peak_interval, max_flood_threat = 0.0, "15m", 0.0
        for interval in NOWCAST_INTERVALS:
            multiplier = multipliers[interval]
            rain_rate = round(max(0.0, min(160.0, base_rain_rate * multiplier)), 1)
            flood = round(max(0.0, min(100.0, min(rain_rate / 60.0, 1.0) * 40.0
                + max(0.0, (20.0 - elevation) / 20.0) * 25.0
                + max(0.0, (100.0 - drainage) / 100.0) * 35.0)), 1)
            if rain_rate > max_rain_rate:
                max_rain_rate, peak_interval = rain_rate, interval
            max_flood_threat = max(max_flood_threat, flood)
            timeline.append({
                "interval": interval,
                "rain_rate_mm_hr": rain_rate,
                "radar_dbz": round(max(5.0, min(68.0, radar_dbz * multiplier * 0.95)), 1),
                "wind_gust_kmh": round(max(10.0, min(110.0, wind_gust * multiplier)), 1),
                "flood_threat_score": flood,
                "thunderstorm_prob": round(min(99.0, hazards["thunderstorms"] * multiplier), 1),
                "confidence": round(0.92 - 0.04 * NOWCAST_INTERVALS.index(interval), 2),
            })

        if max_rain_rate >= 65.0 or max_flood_threat >= 78.0 or hazards["cloudbursts"] >= 65.0:
            alert_level, primary_hazard, advisory = "RED", "CLOUDBURST / EXTREME DOWNPOUR", "Take immediate action. Move to higher floors and avoid waterlogged underpasses."
        elif max_rain_rate >= 35.0 or hazards["thunderstorms"] >= 55.0 or max_flood_threat >= 55.0:
            alert_level, primary_hazard, advisory = "ORANGE", "SEVERE THUNDERSTORM & HEAVY RAIN", "Be prepared. Avoid sheltering under trees or metal structures."
        elif max_rain_rate >= 15.0 or max_flood_threat >= 35.0:
            alert_level, primary_hazard, advisory = "YELLOW", "MODERATE THUNDERSTORM / SHOWERS", "Stay updated and monitor hyper-local weather alerts."
        else:
            alert_level, primary_hazard, advisory = "GREEN", "NORMAL CONDITIONS", "No severe weather alerts active for this zone."

        return {
            "alert_level": alert_level,
            "primary_hazard": primary_hazard,
            "lead_time_minutes": {"2h": 120, "3h": 180, "4h": 240, "5h": 300, "6h": 360}[peak_interval] if max_rain_rate >= 30 else 0,
            "forecast_window_hours": [2, 6],
            "forecast_horizons_hours": [2, 3, 4, 5, 6],
            "peak_interval": peak_interval,
            "max_rain_rate_mm_hr": max_rain_rate,
            "max_flood_threat_score": max_flood_threat,
            "thunderstorm_prob": convective["thunderstorm_prob"],
            "lightning_risk": convective["lightning_risk"],
            "squall_risk": convective["squall_risk"],
            "advisory": advisory,
            "timeline": timeline,
            "hazard_probability_maps": grids,
            "map_shape": [5, 16, 16],
            "xai_triggers": {
                "moisture": {"iwv": float(observation.get("iwv", 45.0)), "iwv_change": float(observation.get("iwv_change", observation.get("iwv_delta", 4.0)))},
                "instability": {"cape_j_kg": float(observation.get("cape_j_kg", 1200.0)), "cin_j_kg": float(observation.get("cin_j_kg", -80.0))},
                "lift_and_structure": {"convergence": float(observation.get("low_level_convergence", 0.12)), "wind_shear_ms": float(observation.get("wind_shear_ms", 12.0))},
                "cloud_growth": {"ctt_drop_rate": float(observation.get("ctt_drop_rate", 2.5))},
                "flood_catalyst": {"elevation_m": float(observation.get("elevation_m", elevation)), "slope_degrees": float(observation.get("slope_degrees", 3.0)), "drainage_score": float(observation.get("drainage_score", drainage))},
            },
        }
