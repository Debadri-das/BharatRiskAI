"""End-to-end inference wrapper for BharatRiskAI's multi-task nowcasting engine."""

from typing import Dict, Any, Optional, Tuple, List
import json
import numpy as np
import torch
from ml.nowcasting.architecture import SpatiotemporalMTLNet
from ml.nowcasting.features import (
    NOWCAST_INTERVALS,
    build_spatiotemporal_features,
    compute_convective_severity,
    extract_features,
)


class NowcastingInferenceEngine:
    """
    Unified interface for multi-task nowcasting inference with XAI feature attribution.
    
    This class:
    1. Loads the pre-trained SpatiotemporalMTLNet model.
    2. Performs end-to-end inference on aligned spatiotemporal grids.
    3. Computes feature attribution scores for XAI transparency.
    4. Returns structured output including hazard risk maps and XAI triggers.
    """
    def set_determinism(self, seed: int = 20260922) -> None:
        """Set random seeds for reproducibility of inference results."""
        import random
        import numpy as np
        import torch
        
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    def __init__(self, device: str = "cpu") -> None:
        self.device = torch.device(device)
        self.model: Optional[SpatiotemporalMTLNet] = None
        self._loaded_checkpoint_path: str | None = None
        self._normalization_stats: Optional[Dict[str, Any]] = None

    def load_artifact(self, path: str) -> None:
        """Load pre-trained model weights from artifact file.

        This is an EXPLICIT call — checkpoint loading must never happen
        implicitly during construction. Callers must invoke this method
        explicitly after creating the engine.

        Args:
            path: Path to the checkpoint file (e.g., models/checkpoints/best.pt).
        """
        if not path:
            raise ValueError("Checkpoint path must be a non-empty string")
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        
        # Validate checkpoint contract
        from reports.checkpoint_contract import validate_checkpoint
        validate_checkpoint(checkpoint)
        
        # Validate embedded normalization before touching model state.  A
        # checkpoint without it is valid when a sidecar scaler is supplied.
        normalization = checkpoint.get("normalization")
        if normalization is not None:
            self._validate_normalization(normalization)

        # Load model state_dict only after all artifact validation succeeds.
        if isinstance(checkpoint, dict) and "model" in checkpoint:
            state_dict = checkpoint["model"]
            input_channels = checkpoint.get("input_channels", 13)
            baseline_channels = checkpoint.get("baseline_channels", 6)
            hidden_channels = checkpoint.get("hidden_channels", 32)
            num_heads = checkpoint.get("num_heads", 4)
            num_layers = checkpoint.get("num_layers", 2)
        else:
            state_dict = checkpoint
            input_channels, baseline_channels, hidden_channels, num_heads, num_layers = 13, 6, 32, 4, 2

        self.model = SpatiotemporalMTLNet(input_channels, baseline_channels, hidden_channels, num_heads, num_layers).to(self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        self._loaded_checkpoint_path = path
        # Prefer embedded training statistics.  Otherwise retain a scaler
        # explicitly loaded by the caller; _assert_ready still blocks use if
        # neither source is available.
        if normalization is not None:
            self._normalization_stats = normalization

    @property
    def checkpoint_path(self) -> str | None:
        """Return the path of the currently loaded checkpoint, or None if no checkpoint has been loaded."""
        return self._loaded_checkpoint_path

    @property
    def is_loaded(self) -> bool:
        """Return True if a checkpoint has been explicitly loaded."""
        return self._loaded_checkpoint_path is not None

    def load_normalization(self, path: str) -> None:
        """Load normalization parameters from scaler.json.

        Args:
            path: Path to the scaler.json file.
        """
        if not path:
            raise ValueError("Normalization path must be a non-empty string")
        
        with open(path, encoding="utf-8") as f:
            normalization_stats = json.load(f)
            
        self._validate_normalization(normalization_stats)
        self._normalization_stats = normalization_stats

    @staticmethod
    def _validate_normalization(normalization_stats: Dict[str, Any]) -> None:
        """Validate the persisted training-only scaler contract."""
        if not isinstance(normalization_stats, dict):
            raise ValueError("Normalization statistics must be a dictionary")
        if normalization_stats.get("method") != "training-only per-channel standardization":
            raise ValueError("Normalization method must be 'training-only per-channel standardization'")
            
        # Ensure we have the correct number of channels
        expected_channels = 19  # 13 dynamic + 6 baseline
        channels = normalization_stats.get("channels")
        if not isinstance(channels, list) or len(channels) != expected_channels:
            count = len(channels) if isinstance(channels, list) else 0
            raise ValueError(f"Expected {expected_channels} channels, got {count}")
        for index, stats in enumerate(normalization_stats["channels"]):
            try:
                valid = (isinstance(stats, dict)
                         and np.isfinite(float(stats.get("mean")))
                         and np.isfinite(float(stats.get("std"))))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f"Invalid normalization statistics for channel {index}")

    @property
    def normalization_stats(self) -> Optional[Dict[str, Any]]:
        """Return the loaded normalization parameters."""
        return self._normalization_stats

    def _normalize_features(self, sequence: np.ndarray, baseline: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply standardization using loaded normalization statistics if available.
        
        Sequence shape: (time_steps, 13, H, W)
        Baseline shape: (6, H, W)
        Total channels: 19 (13 dynamic + 6 baseline)
        """
        if not self._normalization_stats:
            return sequence, baseline

        channels_stats = self._normalization_stats["channels"]
        norm_sequence = sequence.copy()
        norm_baseline = baseline.copy()

        # Normalize 13 sequence channels
        for c in range(sequence.shape[1]):
            mean = channels_stats[c]["mean"]
            std = channels_stats[c]["std"] if channels_stats[c]["std"] > 0 else 1.0
            norm_sequence[:, c, :, :] = (sequence[:, c, :, :] - mean) / std

        # Normalize 6 baseline channels
        seq_channels = sequence.shape[1]
        for c in range(baseline.shape[0]):
            mean = channels_stats[seq_channels + c]["mean"]
            std = channels_stats[seq_channels + c]["std"] if channels_stats[seq_channels + c]["std"] > 0 else 1.0
            norm_baseline[c, :, :] = (baseline[c, :, :] - mean) / std

        return norm_sequence, norm_baseline

    @torch.inference_mode()
    def predict_grid(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Generate multi-task hazard probability maps from observation."""
        self._assert_ready()
        sequence, baseline = build_spatiotemporal_features(observation)
        sequence, baseline = self._normalize_features(sequence, baseline)
        outputs = self.model(
            torch.from_numpy(sequence).unsqueeze(0).to(self.device, dtype=torch.float32),
            torch.from_numpy(baseline).unsqueeze(0).to(self.device, dtype=torch.float32),
        )
        return {
            name: tensor.squeeze(0).cpu().numpy().round(4).tolist()
            for name, tensor in outputs.items()
        }

    def _assert_ready(self) -> None:
        if not self.is_loaded:
            raise RuntimeError("Nowcast inference is unavailable: load a trained checkpoint explicitly")
        if self._normalization_stats is None:
            raise RuntimeError("Nowcast inference is unavailable: load training normalization statistics")

    def compute_feature_attribution(self, observation: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate feature importance scores using gradient-based attribution.
        
        Returns:
            Dictionary of feature names and their normalized contribution scores.
        """
        self._assert_ready()
        sequence, baseline = build_spatiotemporal_features(observation)
        sequence, baseline = self._normalize_features(sequence, baseline)
        sequence_tensor = torch.from_numpy(sequence).unsqueeze(0).to(self.device, dtype=torch.float32).requires_grad_(True)
        baseline_tensor = torch.from_numpy(baseline).unsqueeze(0).to(self.device, dtype=torch.float32)

        outputs = self.model(sequence_tensor, baseline_tensor)
        hazard_map = outputs["thunderstorms"]  # Focus on thunderstorms for attribution

        hazard_map.mean().backward()
        gradients = sequence_tensor.grad.abs().mean(dim=(0, 2, 3, 4)).cpu().numpy()

        feature_importance = gradients / (gradients.sum() + 1e-8)

        # Use the canonical feature order from reports.unified_feature_schema
        from reports.unified_feature_schema import FEATURE_SCHEMA
        feature_names = FEATURE_SCHEMA['insat'] + FEATURE_SCHEMA['imdaa'] + FEATURE_SCHEMA['dem'] + FEATURE_SCHEMA['qpe']
        
        # Fallback to uniform attribution if gradients cannot be computed
        if feature_importance is None or len(feature_importance) != len(feature_names):
            feature_importance = np.ones(len(feature_names)) / len(feature_names)
        
        return dict(zip(feature_names, map(float, feature_importance)))
    def predict_nowcast(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        End-to-end nowcasting inference with XAI feature attribution.
        
        Returns:
            Structured nowcast output including:
            - Hazard probability maps
            - XAI feature attribution scores
            - Convective severity indicators
            - Forecast timeline
            - Alert level and advisory
        """
        scalar_observation = {
            key: (float(value.values.reshape(-1)[-1]) if hasattr(value, "values") else
                  float(value.reshape(-1)[-1]) if isinstance(value, np.ndarray) and value.ndim else value)
            for key, value in observation.items()
        }
        feats = extract_features(scalar_observation)
        convective = compute_convective_severity(scalar_observation)
        grids = self.predict_grid(observation)
        hazards = {name: float(np.max(values) * 100.0) for name, values in grids.items()}

        attribution = self.compute_feature_attribution(observation)

        base_rain_rate, radar_dbz = feats[0], feats[3]
        wind_gust, elevation, drainage = feats[8], feats[10], feats[11]
        multipliers = {"2h": 1.20, "3h": 0.95, "4h": 0.72, "5h": 0.52, "6h": 0.35}
        timeline = []
        max_rain_rate, peak_interval, max_flood_threat = 0.0, "2h", 0.0

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

        xai_triggers = {
            "moisture": {
                 "iwv": float(scalar_observation.get("iwv", 45.0)),
                "attribution": float(attribution["iwv"]),
                "trigger": "Critical moisture accumulation" if attribution["iwv"] > 0.15 else "Normal moisture levels",
            },
            "instability": {
                "cape": float(scalar_observation.get("cape", scalar_observation.get("cape_j_kg", 1200.0))),
                "attribution": float(attribution["cape"]),
                "trigger": "Extreme instability" if attribution["cape"] > 0.12 else "Moderate instability",
            },
            "lift_and_structure": {
                "cape": float(scalar_observation.get("cape", scalar_observation.get("cape_j_kg", 1200.0))),
                "attribution": float(attribution.get("cape", 0.0)),
                "trigger": "Strong instability" if attribution.get("cape", 0.0) > 0.1 else "Weak instability",
            },
            "cloud_growth": {
                "ctt_drop_rate": float(scalar_observation.get("ctt_drop_rate", 2.5)),
                "attribution": float(attribution["ctt_drop_rate"]),
                "trigger": "Explosive updraft" if attribution["ctt_drop_rate"] > 0.1 else "Normal cloud growth",
            },
            "flood_catalyst": {
                "elevation_m": float(scalar_observation.get("elevation_m", elevation)),
                "attribution": float(attribution["elevation"]),
                "trigger": "High flood risk" if attribution["elevation"] > 0.1 else "Low flood risk",
            },
        }

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
            "xai_triggers": xai_triggers,
            "feature_attribution": attribution,
        }
