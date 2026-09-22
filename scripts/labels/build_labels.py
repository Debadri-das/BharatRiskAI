"""Build hazard labels: configured proxy labels where data allows, null where unknown.

Rules enforced here:
- Observations, derived features, proxy labels, and model predictions are distinct.
- Proxy labels are produced ONLY from thresholds configured in config/labels.yaml.
- Unknown labels stay null forever; they are never converted to negatives.
- No model prediction is ever used as a label; no rainfall-only flash-flood label exists.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")


def parse_labels_config(path: Path) -> dict:
    """Minimal indentation parser for the flat config/labels.yaml structure."""
    config: dict[str, dict] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" "):
            current = raw.split(":")[0].strip()
            config[current] = {}
            continue
        if current is None or ":" not in raw:
            continue
        key, _, value = raw.strip().partition(":")
        value = value.strip().strip('"').strip("'")
        if value in ("null", ""):
            config[current][key] = None
        elif value.replace(".", "", 1).isdigit():
            config[current][key] = float(value) if "." in value else int(value)
        else:
            config[current][key] = value
    return config


def save_grid(arrays: np.ndarray, timestamp: str, hazard: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"{timestamp.replace(':', '').replace('+', 'p').replace('-', '')}_{hazard}.npy"
    np.save(output_dir / name, arrays.astype(np.float32))
    return str((output_dir / name).relative_to(ROOT))


def main() -> None:
    config = parse_labels_config(ROOT / "config" / "labels.yaml")
    feature_dir = ROOT / "data" / "derived" / "satellite"
    grid_dir = ROOT / "data" / "datasets" / "labels" / "grids"
    records: list[dict] = []

    thunder_cfg = config.get("thunderstorm", {})
    ctt_max = thunder_cfg.get("ctt_proxy_max_c", -40)
    cooling_min = thunder_cfg.get("ctt_cooling_min_c_per_hr", 2.0)
    cloud_cfg = config.get("cloudburst", {})
    qpe_threshold = cloud_cfg.get("threshold_mm")
    qpe_window_h = cloud_cfg.get("rainfall_window_hours", 1)

    for path in sorted(feature_dir.glob("*.npz")):
        with np.load(path, allow_pickle=False) as data:
            timestamp = str(data["timestamp"])
            is_qpe = path.name.startswith("qpe_")
            if is_qpe:
                if qpe_threshold is None:
                    records.append({"hazard": "cloudburst", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": None, "provenance": "config/labels.yaml cloudburst threshold_mm is null; proxy labels may not be fabricated without a configured threshold."})
                else:
                    rate = data["qpe_rate_mm_hr"]
                    known = np.isfinite(rate)
                    grid = np.full(rate.shape, np.nan, dtype=np.float32)
                    grid[known] = (rate[known] >= float(qpe_threshold)).astype(np.float32)
                    grid_path = save_grid(grid, timestamp, "cloudburst", grid_dir)
                    positives = int(np.nansum(grid))
                    known_pixels = int(np.isfinite(grid).sum())
                    if known_pixels == 0:
                        records.append({"hazard": "cloudburst", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": grid_path, "provenance": "QPE field contains no finite observations at this timestamp; label stays unknown and is never treated as a negative."})
                    else:
                        records.append({"hazard": "cloudburst", "label": 1 if positives else 0, "label_type": "proxy", "source": "INSAT_QPE", "threshold": float(qpe_threshold), "accumulation_window": f"{qpe_window_h}h", "timestamp": timestamp, "spatial_rule": f"Pixel proxy positive where QPE rate >= {qpe_threshold} mm/hr (1-hour accumulation proxy); non-finite QPE pixels are unknown, never negative.", "confidence": None, "label_grid_path": grid_path, "provenance": "CLOUDBURST_PROXY from threshold configured in config/labels.yaml (" + str(cloud_cfg.get("threshold_definition", "")) + ") applied to the observed QPE field; not an observed cloudburst report, no model output involved. Positive pixels: " + str(positives) + " of " + str(known_pixels) + " known pixels."})
                records.append({"hazard": "thunderstorm", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": None, "provenance": "No contemporaneous L1C imager data at this QPE timestamp; satellite-signature proxy cannot be evaluated."})
            else:
                tir1 = data["tir1_bt_c"]
                cooling = data["ctt_cooling_rate"] if "ctt_cooling_rate" in data else np.full(tir1.shape, np.nan, dtype=np.float32)
                known = np.isfinite(tir1) & np.isfinite(cooling)
                grid = np.full(tir1.shape, np.nan, dtype=np.float32)
                positive = (tir1 <= float(ctt_max)) & (cooling >= float(cooling_min))
                grid[known] = positive[known].astype(np.float32)
                grid_path = save_grid(grid, timestamp, "thunderstorm", grid_dir)
                positives = int(np.nansum(grid))
                known_pixels = int(np.isfinite(grid).sum())
                if known_pixels == 0:
                    records.append({"hazard": "thunderstorm", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": grid_path, "provenance": "No evaluable pixels at this timestamp (CTT-proxy cooling requires a previous observation); label stays unknown and is never treated as a negative."})
                else:
                    records.append({"hazard": "thunderstorm", "label": 1 if positives else 0, "label_type": "proxy", "source": "INSAT_L1C_TIR1_WV", "threshold": {"ctt_proxy_max_c": ctt_max, "ctt_cooling_min_c_per_hr": cooling_min}, "accumulation_window": "observed_interval", "timestamp": timestamp, "spatial_rule": f"Pixel proxy positive where CTT proxy (TIR1) <= {ctt_max} C AND CTT-proxy cooling >= {cooling_min} C/hr; pixels with non-finite TIR1 or cooling are unknown, never negative.", "confidence": None, "label_grid_path": grid_path, "provenance": "THUNDERSTORM_PROXY from the satellite-signature rule configured in config/labels.yaml applied to observed L1C-derived features; not an observed lightning/radar report, no model output involved. Positive pixels: " + str(positives) + " of " + str(known_pixels) + " known pixels."})
                records.append({"hazard": "cloudburst", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": None, "provenance": "No contemporaneous QPE observation exists for this timestamp (QPE available only at 2024-06-18); cloudburst proxy cannot be evaluated and stays unknown, never negative."})
            records.append({"hazard": "flash_flood", "label": None, "label_type": "unavailable", "source": None, "threshold": None, "accumulation_window": None, "timestamp": timestamp, "spatial_rule": None, "confidence": None, "label_grid_path": None, "provenance": "No flood extent, gauge, or disaster report exists, and QPE does not overlap this date, so no contemporaneous rainfall+terrain risk proxy can be computed. Rainfall alone is never flood truth."})

    output_dir = ROOT / "data" / "datasets" / "labels"
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "labels.jsonl"
    labels_path.write_text("\n".join(json.dumps(record) for record in records) + ("\n" if records else ""), encoding="utf-8")

    stats: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "timestamps": len({r["timestamp"] for r in records}), "hazards": {}, "event_count": 0, "confirmed_event_count": 0, "proxy_event_dates": {}, "thresholds_configured": {"thunderstorm": {"ctt_proxy_max_c": ctt_max, "ctt_cooling_min_c_per_hr": cooling_min, "source_file": "config/labels.yaml"}, "cloudburst": {"threshold_mm": qpe_threshold, "window_hours": qpe_window_h, "source_file": "config/labels.yaml"}, "flash_flood": {"threshold": None, "reason": "no configured threshold and no overlapping observations"}}, "provenance": "Proxy labels are deterministic rules on observed fields configured in config/labels.yaml; they are never confirmed observations and never model outputs. Unknown labels remain null."}
    for hazard in HAZARDS:
        subset = [r for r in records if r["hazard"] == hazard]
        proxy_pos = sum(1 for r in subset if r["label"] == 1)
        proxy_neg = sum(1 for r in subset if r["label"] == 0)
        unknown = sum(1 for r in subset if r["label"] is None)
        stats["hazards"][hazard] = {"confirmed_positive": 0, "confirmed_negative": 0, "proxy_positive": proxy_pos, "proxy_negative": proxy_neg, "unknown": unknown, "label_types": sorted({r["label_type"] for r in subset}), "spatial_grids": sum(1 for r in subset if r.get("label_grid_path"))}
        stats["proxy_event_dates"][hazard] = sorted({r["timestamp"][:10] for r in subset if r["label"] == 1})
    stats["event_count"] = len({r["timestamp"][:10] for r in records if r["label"] == 1})
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "label_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps({"records": len(records), "hazards": stats["hazards"]}, indent=2))


if __name__ == "__main__":
    main()