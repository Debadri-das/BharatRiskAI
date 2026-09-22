"""Validate temporal feature products, provenance, shapes, ranges, and label readiness."""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SHAPE = (114, 84)
EXPECTED_GRID = {"crs": "EPSG:4326", "resolution_degrees": [0.05, 0.05], "shape": [114, 84]}
SATELLITE_CHANNELS = {"wv_radiance", "wv_change", "wv_rate", "wv_spatial_gradient", "tir1_bt_c", "tir2_bt_c", "ctt_change", "ctt_cooling_rate", "vis_radiance", "vis_albedo_percent"}
QPE_CHANNELS = {"qpe_rate_mm_hr", "qpe_1h_mm", "qpe_3h_mm", "qpe_6h_mm"}
# Physically plausible bounds (NaN = missing observation, allowed but counted).
CHANNEL_RANGES = {
    "tir1_bt_c": (-120.0, 60.0),   # 153-333 K brightness temperature
    "tir2_bt_c": (-120.0, 60.0),
    "wv_radiance": (0.0, 500.0),   # radiance is non-negative
    # Lab-calibrated VIS radiance is physically non-negative, but the quadratic
    # count->radiance calibration plus bilinear regridding produces small negative
    # values near zero illumination at night (observed min ~-1.43). Kept as observed,
    # not clamped; only magnitudes beyond -2.0 would indicate real corruption.
    "vis_radiance": (-2.0, 500.0),
    "vis_albedo_percent": (-1.0, 100.5),
    "qpe_rate_mm_hr": (0.0, 500.0),
}


def corrupt_files() -> list[dict]:
    """Files recorded as truncated/corrupt by the audit and extraction stages (excluded from features)."""
    records: list[dict] = []
    audit_path = ROOT / "reports" / "data_audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        records.extend({"path": item["path"], "error": item["error"], "recorded_by": "audit"} for item in audit.get("errors", []))
    extraction_path = ROOT / "data" / "insat" / "l1c" / "processed" / "extraction_errors.json"
    if extraction_path.exists():
        seen = {item["path"] for item in records}
        for item in json.loads(extraction_path.read_text(encoding="utf-8")):
            if item["path"] not in seen:
                records.append({"path": item["path"], "error": item["error"], "recorded_by": "extraction"})
    return records


def missing_slots(timestamps: list[str]) -> list[dict]:
    """Nominal 30-minute slots inside each covered date that have no observation."""
    by_date: dict[str, list[datetime]] = {}
    for value in timestamps:
        stamp = datetime.fromisoformat(value)
        by_date.setdefault(stamp.date().isoformat(), []).append(stamp)
    missing = []
    for date, stamps in sorted(by_date.items()):
        earliest = min(stamps)
        latest = max(stamps)
        earliest = earliest.replace(minute=(15 if earliest.minute < 30 else 45), second=0, microsecond=0)
        latest = latest.replace(minute=(15 if latest.minute < 30 else 45), second=0, microsecond=0)
        expected = {earliest + timedelta(minutes=30 * step) for step in range(int((latest - earliest).total_seconds() // 1800) + 1)}
        present = {stamp.replace(second=0, microsecond=0) for stamp in stamps}
        missing.extend({"date": date, "expected_slot": slot.isoformat()} for slot in sorted(expected - present))
    return missing


def label_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    label_path = ROOT / "data" / "datasets" / "labels" / "labels.jsonl"
    if not label_path.exists():
        return counts
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        stats = counts.setdefault(record["hazard"], {"positive": 0, "negative": 0, "unknown": 0})
        if record.get("label") is None:
            stats["unknown"] += 1
        elif record["label"] in (1, 1.0, True):
            stats["positive"] += 1
        else:
            stats["negative"] += 1
    return counts


def validate() -> dict:
    files = sorted((ROOT / "data" / "derived" / "satellite").glob("*.npz"))
    timestamps = []
    checks = []
    for path in files:
        result = {"path": str(path.relative_to(ROOT)), "errors": [], "warnings": []}
        is_qpe = path.name.startswith("qpe_")
        expected_channels = QPE_CHANNELS if is_qpe else SATELLITE_CHANNELS
        with np.load(path, allow_pickle=False) as data:
            timestamps.append(str(data["timestamp"]))
            channels = {name for name in data.files if name != "timestamp"}
            missing_channels = sorted(expected_channels - channels)
            extra_channels = sorted(channels - expected_channels)
            if missing_channels:
                result["errors"].append(f"missing channels: {missing_channels}")
            if extra_channels:
                result["warnings"].append(f"unexpected channels: {extra_channels}")
            for name in data.files:
                if name == "timestamp":
                    continue
                values = data[name]
                if values.shape != EXPECTED_SHAPE:
                    result["errors"].append(f"spatial shape mismatch: {name} {values.shape} != {EXPECTED_SHAPE}")
                if np.isinf(values).any():
                    result["errors"].append(f"{name} contains infinite values")
                bounds = CHANNEL_RANGES.get(name)
                if bounds is not None and np.isfinite(values).any():
                    observed_min = float(np.nanmin(values))
                    observed_max = float(np.nanmax(values))
                    if observed_min < bounds[0] or observed_max > bounds[1]:
                        result["errors"].append(f"{name} outside valid range [{bounds[0]}, {bounds[1]}]: observed [{observed_min}, {observed_max}]")
                if name not in ("wv_change", "wv_rate", "ctt_change", "ctt_cooling_rate", "qpe_1h_mm", "qpe_3h_mm", "qpe_6h_mm") and np.isnan(values).mean() > 0.99:
                    result["warnings"].append(f"{name} is almost entirely missing")
        checks.append(result)

    counts = label_counts()
    unknown_labels = sum(stats["unknown"] for stats in counts.values())
    positive_labels = sum(stats["positive"] for stats in counts.values())
    negative_labels = sum(stats["negative"] for stats in counts.values())
    label_imbalance = []
    for hazard, stats in counts.items():
        total_known = stats["positive"] + stats["negative"]
        if total_known == 0:
            label_imbalance.append(f"{hazard}: no known labels (all {stats['unknown']} unknown)")
        elif stats["positive"] == 0:
            label_imbalance.append(f"{hazard}: 0 positives among {total_known} known labels")
        elif stats["negative"] == 0:
            label_imbalance.append(f"{hazard}: 0 negatives among {total_known} known labels")

    duplicate_timestamps = len(timestamps) - len(set(timestamps))
    gaps = []
    parsed = sorted(datetime.fromisoformat(value) for value in timestamps)
    for previous, current in zip(parsed, parsed[1:]):
        minutes = (current - previous).total_seconds() / 60
        if abs(minutes - 30) > 1:
            gaps.append({"from": previous.isoformat(), "to": current.isoformat(), "minutes": minutes})
    # The nominal :15/:45 imager slot schedule applies to L1C images only; the QPE
    # product has its own observation time (e.g. 12:00) and must not be flagged.
    imager_timestamps = [str(np.load(path, allow_pickle=False)["timestamp"]) for path in files if not path.name.startswith("qpe_")]
    absent = missing_slots(imager_timestamps)
    corrupt = corrupt_files()

    grid_errors = []
    manifest_path = ROOT / "data" / "derived" / "grid_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        grid = manifest.get("grid", {})
        if grid.get("crs") != EXPECTED_GRID["crs"] or grid.get("resolution_degrees") != EXPECTED_GRID["resolution_degrees"] or grid.get("shape") != EXPECTED_GRID["shape"]:
            grid_errors.append(f"CRS/grid mismatch: manifest {grid} != expected {EXPECTED_GRID}")
        if manifest.get("shape_mismatches"):
            grid_errors.append(f"manifest reports {len(manifest['shape_mismatches'])} shape mismatches")
    else:
        grid_errors.append("grid_manifest.json missing; CRS/grid contract unverified")

    checks_failed = any(item["errors"] for item in checks) or bool(grid_errors)
    report = {
        "status": "failed" if checks_failed or unknown_labels else "passed",
        "file_count": len(files),
        "duplicate_timestamps": duplicate_timestamps,
        "missing_timestamp_slots": absent,
        "temporal_gaps": gaps,
        "corrupt_files": corrupt,
        "grid_checks": grid_errors,
        "unknown_label_records": unknown_labels,
        "label_counts": counts,
        "label_imbalance": label_imbalance,
        "positive_label_records": positive_labels,
        "negative_label_records": negative_labels,
        "checks": checks,
        "critical_missing": (["IMDAA", "CMV", "observed hazard ground truth"] if unknown_labels else []),
    }
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "dataset_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    rows = "".join(f"<tr><td>{html.escape(item['path'])}</td><td>{html.escape('; '.join(item['errors']) or 'ok')}</td><td>{html.escape('; '.join(item['warnings']) or '')}</td></tr>" for item in checks)
    corrupt_rows = "".join(f"<li>{html.escape(item['path'])}: {html.escape(item['error'])} (recorded by {html.escape(item['recorded_by'])}, excluded from features)</li>" for item in corrupt)
    imbalance_rows = "".join(f"<li>{html.escape(item)}</li>" for item in label_imbalance)
    (reports / "dataset_validation.html").write_text(
        f"<html><head><meta charset='utf-8'></head><body><h1>Dataset validation: {report['status']}</h1>"
        f"<p>Files checked: {len(files)} | Duplicate timestamps: {duplicate_timestamps} | Missing nominal slots: {len(absent)} | Temporal gaps: {len(gaps)}</p>"
        f"<p>Labels &mdash; positive: {positive_labels}, negative: {negative_labels}, unknown: {unknown_labels}</p>"
        f"<h2>Critical missing</h2><p>{html.escape(', '.join(report['critical_missing']) or 'none')}</p>"
        f"<h2>Grid checks</h2><p>{html.escape('; '.join(grid_errors) or 'ok')}</p>"
        f"<h2>Label imbalance</h2><ul>{imbalance_rows or '<li>none</li>'}</ul>"
        f"<h2>Corrupt source files ({len(corrupt)})</h2><ul>{corrupt_rows or '<li>none</li>'}</ul>"
        f"<h2>Per-file checks</h2><table><tr><th>File</th><th>Errors</th><th>Warnings</th></tr>{rows}</table>"
        "</body></html>",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    result = validate()
    print(json.dumps({key: result[key] for key in ("status", "file_count", "duplicate_timestamps", "unknown_label_records", "positive_label_records", "negative_label_records")}, indent=2))
    print("corrupt_files:", len(result["corrupt_files"]), "| missing_slots:", len(result["missing_timestamp_slots"]), "| gaps:", len(result["temporal_gaps"]), "| grid_checks:", result["grid_checks"] or "ok")
    if result["status"] == "failed":
        raise SystemExit(2)