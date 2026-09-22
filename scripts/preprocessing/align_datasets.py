"""Write the common-grid contract and verify processed feature shapes."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GRID = {"crs": "EPSG:4326", "resolution_degrees": [0.05, 0.05], "extent": {"west": 85.7, "south": 21.5, "east": 89.9, "north": 27.2}, "shape": [114, 84], "temporal_interval_minutes": 30}


def jitter_and_gaps(timestamps: list[str]) -> tuple[list[dict], list[dict]]:
    """Separate provider clock jitter (seconds from the nominal 30-min slot) from real temporal gaps (missing observations)."""
    parsed = [datetime.fromisoformat(value) for value in timestamps]
    jitter: list[dict] = []
    for stamp in parsed:
        # Nominal INSAT slots are :15 and :45 past the hour.
        nominal = stamp.replace(minute=(15 if stamp.minute < 30 else 45), second=0, microsecond=0)
        offset = (stamp - nominal).total_seconds()
        if abs(offset) > 0:
            jitter.append({"timestamp": stamp.isoformat(), "offset_seconds_from_nominal_slot": offset})
    gaps: list[dict] = []
    for previous, current in zip(parsed, parsed[1:]):
        delta = current - previous
        if delta > timedelta(minutes=GRID["temporal_interval_minutes"] * 1.25):
            gaps.append({"from": previous.isoformat(), "to": current.isoformat(), "minutes": delta.total_seconds() / 60.0, "missing_slots": int(delta // timedelta(minutes=GRID["temporal_interval_minutes"])) - 1})
    return jitter, gaps


def main() -> None:
    feature_dir = ROOT / "data" / "derived" / "satellite"
    files = sorted(feature_dir.glob("*.npz"))
    mismatches = []
    timestamps = []
    for path in files:
        with np.load(path, allow_pickle=False) as data:
            timestamps.append(str(data["timestamp"]))
            shapes = {name: list(data[name].shape) for name in data.files if name != "timestamp"}
            if any(shape != GRID["shape"] for shape in shapes.values()):
                mismatches.append({"path": str(path.relative_to(ROOT)), "shapes": shapes})
    jitter, gaps = jitter_and_gaps(timestamps)
    output = ROOT / "data" / "derived" / "grid_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "grid": GRID, "file_count": len(files), "timestamps": timestamps, "shape_mismatches": mismatches, "provider_timestamp_jitter": jitter, "temporal_gaps": gaps, "qpe_temporal_note": "The available QPE sample is 2024-06-18 and does not overlap the 2023-07-01 L1C sequence; it is not joined as a contemporaneous feature."}, indent=2), encoding="utf-8")
    if mismatches:
        raise RuntimeError(f"Common-grid validation failed for {len(mismatches)} files")
    print(output)


if __name__ == "__main__":
    main()
