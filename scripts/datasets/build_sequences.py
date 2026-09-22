"""Construct temporal samples only when target labels are known."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    labels_path = ROOT / "data" / "datasets" / "labels" / "labels.jsonl"
    records = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()] if labels_path.exists() else []
    unknown = sum(record.get("label") is None for record in records)
    split_dir = ROOT / "data" / "datasets" / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    fields = ["event_id", "timestamp", "spatial_tile", "input_sequence", "target_sequence", "hazard_labels", "split"]
    for name in ("train", "validation", "test"):
        with (split_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()
    if unknown:
        report = blocked_readiness(records)
        (ROOT / "reports" / "data_readiness.md").write_text(report["markdown"], encoding="utf-8")
        (ROOT / "reports" / "data_readiness.json").write_text(json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2), encoding="utf-8")
        raise RuntimeError(json.dumps({"status": "blocked", "reason": "Cannot build supervised sequences while target labels are unknown; null is not a negative label.", "unknown_label_records": unknown, "next_action": "Provide official event observations or configure a documented proxy threshold and rerun labels."}))
    feature_files = sorted((ROOT / "data" / "derived" / "satellite").glob("*.npz"), key=lambda path: str(np.load(path, allow_pickle=False)["timestamp"]))
    label_grids = {(record["timestamp"], record["hazard"]): record.get("label_grid_path") for record in records}
    by_timestamp = {str(np.load(path, allow_pickle=False)["timestamp"]): path for path in feature_files}
    timestamps = sorted(by_timestamp)
    required_offsets = list(range(-6, 1))
    horizons = [4, 6, 8, 10, 12]
    samples = []
    for index in range(6, len(timestamps) - max(horizons)):
        input_times = timestamps[index - 6:index + 1]
        target_times = [timestamps[index + offset] for offset in horizons]
        if any((datetime.fromisoformat(input_times[offset + 1]) - datetime.fromisoformat(input_times[offset])).total_seconds() != 1800 for offset in range(6)):
            continue
        if any(time not in by_timestamp for time in target_times):
            continue
        inputs = []
        for time in input_times:
            with np.load(by_timestamp[time], allow_pickle=False) as data:
                inputs.append(np.stack([data[name] for name in data.files if name != "timestamp"]))
        input_array = np.stack(inputs).astype(np.float32)
        target_layers = []
        for target_time in target_times:
            hazard_layers = []
            for hazard in ("thunderstorm", "cloudburst", "flash_flood"):
                grid_path = label_grids.get((target_time, hazard))
                if not grid_path:
                    raise RuntimeError(f"Missing spatial label grid for {hazard} at {target_time}; scalar labels cannot be expanded into spatial ground truth.")
                grid = np.load(ROOT / grid_path, allow_pickle=False)
                if grid.shape != input_array.shape[-2:]:
                    raise RuntimeError(f"Label grid shape {grid.shape} does not match feature grid {input_array.shape[-2:]}")
                hazard_layers.append(grid.astype(np.float32))
            target_layers.append(np.stack(hazard_layers))
        target_array = np.stack(target_layers)
        sample_dir = ROOT / "data" / "datasets" / "sequences"
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_path = sample_dir / f"sample_{index:05d}.npz"
        np.savez_compressed(sample_path, inputs=input_array, targets=target_array, timestamp=timestamps[index])
        samples.append({"event_id": timestamps[index][:10], "timestamp": timestamps[index], "input_path": str(sample_path.relative_to(ROOT)), "target_path": str(sample_path.relative_to(ROOT)), "split": "unassigned", "hazard_label_summary": "known labels required"})
    if not samples:
        raise RuntimeError("No valid 7-frame/5-horizon sequences can be constructed from the available timestamps.")
    dates = sorted({row["event_id"] for row in samples})
    if len(dates) < 3:
        raise RuntimeError(f"Event/date split blocked: only {len(dates)} independent date group is available; at least 3 are required for train/validation/test.")
    # Event/date-group split: whole dates stay in exactly one split so frames from
    # the same day never leak across train/validation/test.
    train_dates = set(dates[: max(1, int(len(dates) * 0.7))])
    validation_dates = set(dates[max(1, int(len(dates) * 0.7)): max(2, int(len(dates) * 0.85))])
    for row in samples:
        if row["event_id"] in train_dates:
            row["split"] = "train"
        elif row["event_id"] in validation_dates:
            row["split"] = "validation"
        else:
            row["split"] = "test"
    final_dir = ROOT / "data" / "datasets" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    with (final_dir / "index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=samples[0].keys())
        writer.writeheader()
        writer.writerows(samples)


def blocked_readiness(records: list[dict]) -> dict:
    """Compose the data-readiness report required before any supervised stage can run."""
    timestamps = sorted({record["timestamp"] for record in records})
    dates = sorted({value[:10] for value in timestamps})
    per_hazard: dict[str, dict[str, int]] = {}
    for record in records:
        stats = per_hazard.setdefault(record["hazard"], {"confirmed_positive": 0, "confirmed_negative": 0, "proxy_positive": 0, "proxy_negative": 0, "positive": 0, "negative": 0, "unknown": 0})
        if record.get("label") is None:
            stats["unknown"] += 1
            continue
        key = "positive" if record["label"] in (1, 1.0, True) else "negative"
        stats[key] += 1
        kind = "proxy" if record.get("label_type") == "proxy" else "confirmed"
        stats[f"{kind}_{key}"] += 1
    missing_sources = ["IMDAA pressure-level reanalysis (data/imdaa)", "CMV cloud-motion vectors (data/insat/cmv, optional)", "official lightning/thunderstorm event catalogue", "official cloudburst event catalogue with authoritative threshold", "official flood/inundation observations (gauge, extent, or disaster reports)", "contemporaneous multi-date INSAT L1C + QPE sequences"]
    required = [
        "INSAT-3DR L1C imager granules for at least 3+ independent dates covering real weather events (thunderstorm, cloudburst, and flood episodes), each with a full 30-minute sequence usable for +2h..+6h horizons.",
        "Contemporaneous INSAT QPE (HEM) for those same dates so 1h/3h/6h accumulations can be computed from actual timestamps.",
        "IMDAA pressure-level profiles (temperature, humidity, pressure, u/v wind) for the same dates to derive IWV, CAPE, CIN, shear, and convergence.",
        "At least one authoritative thunderstorm/lightning observation source (e.g., lightning detection network or IMD storm reports) to create confirmed thunderstorm labels.",
        "An authoritative cloudburst definition/threshold plus observed rainfall reports for label confirmation.",
        "Official flood/inundation observations (gauge exceedance, satellite-derived flood extent, or disaster management reports) for flash-flood labels.",
        "Optional: INSAT CMV products for atmospheric motion features.",
    ]
    lines = [
        "# Data readiness", "",
        "## Status", "",
        "Blocked for supervised training: " + str(sum(v["unknown"] for v in per_hazard.values())) + " hazard-timestamp targets remain unknown (null means unknown, never negative) and 0 confirmed labels exist. Configured proxy labels (thunderstorm satellite signature, cloudburst QPE threshold) are recorded as label_type=proxy and never presented as observed truth; flash_flood has no evaluable overlapping input at all, so supervised sequences cannot be completed.", "",
        "- Timestamp count (feature grids): " + str(len(timestamps)),
        "- Date range: " + (f"{timestamps[0]} to {timestamps[-1]}" if timestamps else "n/a"),
        "- Independent dates/events: " + str(len(dates)) + (" (only 1 usable L1C date; the single QPE sample is a separate date)" if len(dates) <= 2 else ""),
        "- Positive labels: " + str(sum(v["positive"] for v in per_hazard.values())),
        "- Negative labels: " + str(sum(v["negative"] for v in per_hazard.values())),
        "- Unknown labels: " + str(sum(v["unknown"] for v in per_hazard.values())),
        "- Per hazard: " + json.dumps(per_hazard),
        "- Ground-truth event sources: none",
        "- IMDAA: missing", "- CMV: missing",
        "- Official thunderstorm, cloudburst, and flood records: missing",
        "- Train/validation/test feasibility: not feasible (0/0/0); fewer than 3 independent event/date groups exist and hazard targets remain incomplete (unknown records), so no split is created.", "",
        "## Missing sources", "",
    ]
    lines.extend(f"- {item}" for item in missing_sources)
    lines.extend(["", "## Exact additional data required before meaningful training", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(required, start=1))
    lines.extend(["", "A smoke-test model may exercise tensor plumbing only; it must not be reported as trained or evaluated.", ""])
    return {"status": "blocked", "timestamp_count": len(timestamps), "date_range": [timestamps[0], timestamps[-1]] if timestamps else [], "independent_dates": len(dates), "labels": per_hazard, "missing_sources": missing_sources, "split_feasibility": {"train": 0, "validation": 0, "test": 0, "feasible": False}, "required_additional_data": required, "markdown": "\n".join(lines)}


if __name__ == "__main__":
    main()
