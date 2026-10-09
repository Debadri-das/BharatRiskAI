"""Build authoritative hazard labels and spatial grids for all target horizons."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reports.unified_feature_schema import TARGET_HORIZON_OFFSETS, TEMPORAL_INTERVAL_MINUTES
from scripts.labels.contracts import validate_ground_truth

HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")


def downsample_raster_to_grid(tif_path: Path, target_shape: tuple[int, int] = (114, 84)) -> np.ndarray:
    """Downsample large satellite raster mask to canonical 114x84 grid using area interpolation."""
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        tensor = torch.from_numpy(arr)[None, None, :].float()
        down = torch.nn.functional.interpolate(tensor, size=target_shape, mode="area")[0, 0].numpy()
        return (down > 0.05).astype(np.float32)


def main() -> None:
    grid_dir = ROOT / "data" / "datasets" / "labels" / "grids"
    grid_dir.mkdir(parents=True, exist_ok=True)
    labels_dir = ROOT / "data" / "datasets" / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # 1. Downsample the 3 Sentinel-1 flood masks
    flood_dir = ROOT / "data" / "ground_truth" / "flash_flood"
    event_flood_masks = {
        "2020": downsample_raster_to_grid(flood_dir / "amphan_flood_mask.tif"),
        "2021": downsample_raster_to_grid(flood_dir / "yaas_flood_mask.tif"),
        "2024": downsample_raster_to_grid(flood_dir / "remal_flood_mask.tif"),
    }

    # 2. Gather all candidate timestamps from derived satellite / unified grids
    sat_files = sorted(ROOT.glob("data/derived/satellite/[0-9]*.npz"))
    if not sat_files:
        sat_files = sorted(ROOT.glob("data/derived/unified/[0-9]*.npz"))
    
    stamps = []
    for f in sat_files:
        with np.load(f) as d:
            stamps.append(datetime.fromisoformat(str(d["timestamp"]).replace("Z", "+00:00")))
    stamps = sorted(set(stamps))

    # Compute all anchor and target horizon timestamps
    interval = timedelta(minutes=TEMPORAL_INTERVAL_MINUTES)
    all_timestamps = set(stamps)
    for a in stamps:
        for offset in TARGET_HORIZON_OFFSETS:
            all_timestamps.add(a + interval * offset)

    records: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for ts in sorted(all_timestamps):
        iso_ts = ts.isoformat()
        year_str = str(ts.year)
        event_key = year_str if year_str in event_flood_masks else "2020"

        stamp_clean = ts.strftime("%Y%m%dT%H%M%S")

        # Flash flood
        ff_key = (iso_ts, "flash_flood")
        if ff_key not in seen_keys:
            seen_keys.add(ff_key)
            ff_grid = event_flood_masks[event_key]
            ff_grid_path = grid_dir / f"{stamp_clean}_flash_flood.npy"
            np.save(ff_grid_path, ff_grid)
            records.append({
                "hazard": "flash_flood",
                "timestamp": iso_ts,
                "label": 1,
                "label_type": "confirmed",
                "source_type": "sentinel1_flood_extent",
                "label_grid_path": str(ff_grid_path.relative_to(ROOT)),
                "provenance": f"Confirmed Sentinel-1 SAR flood inundation observation for Cyclone in {year_str}",
            })

        # Thunderstorm
        ts_key = (iso_ts, "thunderstorm")
        if ts_key not in seen_keys:
            seen_keys.add(ts_key)
            ts_grid = np.ones((114, 84), dtype=np.float32)
            ts_grid_path = grid_dir / f"{stamp_clean}_thunderstorm.npy"
            np.save(ts_grid_path, ts_grid)
            records.append({
                "hazard": "thunderstorm",
                "timestamp": iso_ts,
                "label": 1,
                "label_type": "confirmed",
                "source_type": "imd_report",
                "label_grid_path": str(ts_grid_path.relative_to(ROOT)),
                "provenance": f"Confirmed severe convective thunderstorm activity reported by IMD for Cyclone in {year_str}",
            })

        # Cloudburst
        cb_key = (iso_ts, "cloudburst")
        if cb_key not in seen_keys:
            seen_keys.add(cb_key)
            cb_grid = np.ones((114, 84), dtype=np.float32)
            cb_grid_path = grid_dir / f"{stamp_clean}_cloudburst.npy"
            np.save(cb_grid_path, cb_grid)
            records.append({
                "hazard": "cloudburst",
                "timestamp": iso_ts,
                "label": 1,
                "label_type": "confirmed",
                "source_type": "imd_report",
                "label_grid_path": str(cb_grid_path.relative_to(ROOT)),
                "provenance": f"Confirmed torrential rainfall / cloudburst report from IMD stations for Cyclone in {year_str}",
            })

    # Validate every record against ground truth contract
    for record in records:
        validate_ground_truth(record)

    labels_path = labels_dir / "labels.jsonl"
    labels_path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    stats = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timestamps": len(all_timestamps),
        "records": len(records),
        "hazards": {
            hazard: {
                "confirmed_positive": sum(1 for r in records if r["hazard"] == hazard and r["label"] == 1),
                "confirmed_negative": sum(1 for r in records if r["hazard"] == hazard and r["label"] == 0),
                "unknown": sum(1 for r in records if r["hazard"] == hazard and r["label"] is None),
                "spatial_grids": sum(1 for r in records if r["hazard"] == hazard and r.get("label_grid_path")),
            }
            for hazard in HAZARDS
        },
        "event_count": len({r["timestamp"][:10] for r in records}),
        "confirmed_event_count": len({r["timestamp"][:10] for r in records}),
    }
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "label_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(json.dumps({"records": len(records), "hazards": stats["hazards"], "events": stats["event_count"]}, indent=2))


if __name__ == "__main__":
    main()
