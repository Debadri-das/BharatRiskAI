"""Construct temporal samples only when target labels are known."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from reports.unified_feature_schema import (
    CHANNEL_ORDER,
    INPUT_FRAME_COUNT,
    TARGET_HORIZON_OFFSETS,
    TEMPORAL_INTERVAL_MINUTES,
)
from reports.source_manifest import manifest_summary
from scripts.labels.contracts import LabelContractError, validate_ground_truth

ROOT = Path(__file__).resolve().parents[2]
HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")


def _timestamp(value: Any) -> datetime:
    """Parse a timestamp without silently changing its timezone or cadence."""
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def discover_aligned_feature_grids(feature_dir: Path) -> dict[datetime, Path]:
    """Discover timestamped, canonical-channel feature grids deterministically.

    Every product must contain all channels in ``CHANNEL_ORDER`` and every
    channel must be a 2-D grid.  Missing channels, duplicate timestamps, and
    malformed products are hard errors: this stage never invents weather data.
    """
    paths = sorted(Path(feature_dir).rglob("*.npz"))
    if not paths:
        raise ValueError(f"No timestamped feature grids found in {feature_dir}")
    found: dict[datetime, Path] = {}
    shapes: set[tuple[int, int]] = set()
    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            if "timestamp" not in data.files:
                raise ValueError(f"Feature grid {path} has no timestamp")
            stamp = _timestamp(data["timestamp"].item() if data["timestamp"].ndim == 0 else data["timestamp"][0])
            missing = [name for name in CHANNEL_ORDER if name not in data.files]
            unknown = [name for name in data.files if name != "timestamp" and name not in CHANNEL_ORDER]
            if missing or unknown:
                raise ValueError(f"Feature grid {path} channel contract failed; missing={missing}, unknown={unknown}")
            local_shapes = {tuple(data[name].shape) for name in CHANNEL_ORDER}
            if len(local_shapes) != 1 or next(iter(local_shapes), ()) == () or len(next(iter(local_shapes), ())) != 2:
                raise ValueError(f"Feature grid {path} channels must be same 2-D shape")
            shape = next(iter(local_shapes))
            shapes.add(shape)
            if stamp in found:
                raise ValueError(f"Duplicate feature timestamp {stamp.isoformat()}: {found[stamp]} and {path}")
            found[stamp] = path
    if len(shapes) != 1:
        raise ValueError(f"Feature grids have inconsistent spatial shapes: {sorted(shapes)}")
    return dict(sorted(found.items()))


def _label_lookup(labels: Iterable[Mapping[str, Any]], root: Path) -> dict[tuple[datetime, str], Path]:
    lookup: dict[tuple[datetime, str], Path] = {}
    for record in labels:
        hazard = record.get("hazard")
        if hazard not in HAZARDS:
            raise ValueError(f"Unsupported or missing hazard label: {hazard!r}")
        label = record.get("label")
        if label is None or label not in (0, 1, 0.0, 1.0, False, True):
            raise ValueError(f"Unknown or invalid label for {hazard} at {record.get('timestamp')}")
        if record.get("label_type") not in (None, "confirmed"):
            raise ValueError(f"Non-ground-truth label cannot build supervised sequence: {record}")
        grid_path = record.get("label_grid_path")
        if not grid_path:
            raise ValueError(f"Missing spatial label grid for {hazard} at {record.get('timestamp')}")
        path = Path(grid_path)
        if not path.is_absolute():
            path = root / path
        key = (_timestamp(record["timestamp"]), hazard)
        if key in lookup:
            raise ValueError(f"Duplicate label for {key[1]} at {key[0].isoformat()}")
        lookup[key] = path
    return lookup


def assemble_sequences(
    feature_dir: Path,
    labels: Iterable[Mapping[str, Any]],
    *,
    label_root: Path | None = None,
    output_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Assemble canonical ``(7 frames, +2..+6h)`` samples from real products."""
    feature_dir = Path(feature_dir)
    grids = discover_aligned_feature_grids(feature_dir)
    label_lookup = _label_lookup(labels, Path(label_root or feature_dir))
    interval = timedelta(minutes=TEMPORAL_INTERVAL_MINUTES)
    stamps = list(grids)
    by_stamp = set(stamps)
    samples: list[dict[str, Any]] = []
    for anchor in stamps:
        input_times = [anchor - interval * offset for offset in range(INPUT_FRAME_COUNT - 1, -1, -1)]
        target_times = [anchor + interval * offset for offset in TARGET_HORIZON_OFFSETS]
        if any(stamp not in by_stamp for stamp in input_times):
            continue
        # A target timestamp need not have a feature product; labels still must
        # exist, and target grids are loaded below.  This keeps labels explicit.
        inputs: list[np.ndarray] = []
        for stamp in input_times:
            with np.load(grids[stamp], allow_pickle=False) as data:
                inputs.append(np.stack([np.asarray(data[name], dtype=np.float32) for name in CHANNEL_ORDER]))
        input_array = np.stack(inputs)
        target_layers: list[np.ndarray] = []
        for target_time in target_times:
            hazard_layers: list[np.ndarray] = []
            for hazard in HAZARDS:
                path = label_lookup.get((target_time, hazard))
                if path is None:
                    raise ValueError(f"Missing spatial label grid for {hazard} at {target_time.isoformat()}")
                grid_data = np.load(path, allow_pickle=False)
                if isinstance(grid_data, np.lib.npyio.NpzFile):
                    if "grid" not in grid_data.files:
                        grid_data.close()
                        raise ValueError(f"Label product {path} must contain a 'grid' array")
                    grid = np.asarray(grid_data["grid"], dtype=np.float32)
                    grid_data.close()
                else:
                    grid = np.asarray(grid_data, dtype=np.float32)
                if grid.shape != input_array.shape[-2:]:
                    raise ValueError(f"Label grid shape {grid.shape} does not match feature grid {input_array.shape[-2:]}")
                hazard_layers.append(grid)
            target_layers.append(np.stack(hazard_layers))
        target_array = np.stack(target_layers)
        row: dict[str, Any] = {"timestamp": anchor.isoformat(), "inputs": input_array, "targets": target_array}
        if output_dir is not None:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            path = Path(output_dir) / f"sample_{len(samples):05d}.npz"
            np.savez_compressed(path, inputs=input_array, targets=target_array, timestamp=anchor.isoformat())
            row["path"] = path
        samples.append(row)
    if not samples:
        raise ValueError("No valid 7-frame/5-horizon sequences can be constructed from available timestamps")
    return samples


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build canonical 7-frame, +2h..+6h sequences")
    parser.add_argument("--features", type=Path, default=ROOT / "data" / "derived" / "satellite")
    parser.add_argument("--labels", type=Path, default=ROOT / "data" / "datasets" / "labels" / "labels.jsonl")
    parser.add_argument("--label-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "datasets" / "sequences")
    args = parser.parse_args(argv)
    labels_path = args.labels
    records = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()] if labels_path.exists() else []
    unknown = sum(record.get("label") is None for record in records)
    invalid = [record for record in records if record.get("label") is not None and record.get("label") not in (0, 1, 0.0, 1.0, False, True)]
    contract_invalid = []
    for record in records:
        # Proxy/unavailable records are produced by the predictor-label stage;
        # confirmed records must pass the independent observation contract.
        if record.get("label_type") == "confirmed":
            try:
                validate_ground_truth(record)
            except LabelContractError as exc:
                contract_invalid.append({"record": record, "reason": str(exc)})
    split_dir = ROOT / "data" / "datasets" / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    fields = ["event_id", "timestamp", "spatial_tile", "input_sequence", "target_sequence", "hazard_labels", "split"]
    for name in ("train", "validation", "test"):
        with (split_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()
    if unknown or invalid or contract_invalid:
        report = blocked_readiness(records)
        (ROOT / "reports" / "data_readiness.md").write_text(report["markdown"], encoding="utf-8")
        (ROOT / "reports" / "data_readiness.json").write_text(json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2), encoding="utf-8")
        raise RuntimeError(json.dumps({"status": "blocked", "reason": "Cannot build supervised sequences with unknown, invalid, or contract-invalid targets; null is not a negative label.", "unknown_label_records": unknown, "invalid_label_records": len(invalid), "contract_invalid_records": len(contract_invalid), "next_action": "Provide independent lightning/rainfall/flood observations; QPE and IMERG may support but cannot be confirmed truth."}))
    built = assemble_sequences(args.features, records, label_root=args.label_root, output_dir=args.output)
    samples = [{"event_id": row["timestamp"][:10], "timestamp": row["timestamp"], "input_path": str(Path(row["path"]).relative_to(ROOT)) if "path" in row else "", "target_path": str(Path(row["path"]).relative_to(ROOT)) if "path" in row else "", "split": "unassigned", "hazard_label_summary": "known labels required"} for row in built]
    if not samples:
        raise RuntimeError("No valid 7-frame/5-horizon sequences can be constructed from the available timestamps.")
    dates = sorted({row["event_id"] for row in samples})
    if len(dates) < 3:
        raise RuntimeError(f"Event/date split blocked: only {len(dates)} independent date group is available; at least 3 are required for train/validation/test.")
    # Event/date-group split: whole dates stay in exactly one split so frames from
    # the same day never leak across train/validation/test.
    train_dates = set(dates[: max(1, int(len(dates) * 0.7))])
    val_start = max(1, int(len(dates) * 0.7))
    val_end = max(val_start + 1, int(len(dates) * 0.85))
    validation_dates = set(dates[val_start:val_end])
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
        if record["label"] not in (0, 1, 0.0, 1.0, False, True):
            stats.setdefault("invalid", 0)
            stats["invalid"] += 1
            continue
        key = "positive" if record["label"] in (1, 1.0, True) else "negative"
        stats[key] += 1
        kind = "proxy" if record.get("label_type") == "proxy" else "confirmed"
        stats[f"{kind}_{key}"] += 1
    source_manifest = manifest_summary(ROOT)
    missing_sources = [f"{name} (required source)" for name in source_manifest["missing_required"]]
    missing_sources.extend(["official lightning/thunderstorm event catalogue", "official cloudburst event catalogue with authoritative threshold", "official flood/inundation observations (gauge, extent, or disaster reports)", "contemporaneous multi-date INSAT L1C + QPE sequences"])
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
        "Blocked for supervised training: " + str(sum(v["unknown"] for v in per_hazard.values())) + " hazard-timestamp targets remain unknown (null means unknown, never negative), or labels are invalid. Configured proxy labels (thunderstorm satellite signature, cloudburst QPE threshold) are recorded as label_type=proxy and never presented as observed truth; flash_flood has no evaluable overlapping input at all, so supervised sequences cannot be completed.", "",
        "- Timestamp count (feature grids): " + str(len(timestamps)),
        "- Date range: " + (f"{timestamps[0]} to {timestamps[-1]}" if timestamps else "n/a"),
        "- Independent dates/events: " + str(len(dates)) + (" (only 1 usable L1C date; the single QPE sample is a separate date)" if len(dates) <= 2 else ""),
        "- Positive labels: " + str(sum(v["positive"] for v in per_hazard.values())),
        "- Negative labels: " + str(sum(v["negative"] for v in per_hazard.values())),
        "- Unknown labels: " + str(sum(v["unknown"] for v in per_hazard.values())),
        "- Per hazard: " + json.dumps(per_hazard),
        "- Ground-truth event sources: none",
        "- Source manifest: " + json.dumps({name: item["status"] for name, item in source_manifest["sources"].items()}),
        "- Official thunderstorm, cloudburst, and flood records: missing",
        "- Train/validation/test feasibility: not feasible (0/0/0); fewer than 3 independent event/date groups exist and hazard targets remain incomplete (unknown records), so no split is created.", "",
        "## Missing sources", "",
    ]
    lines.extend(f"- {item}" for item in missing_sources)
    lines.extend(["", "## Exact additional data required before meaningful training", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(required, start=1))
    lines.extend(["", "A smoke-test model may exercise tensor plumbing only; it must not be reported as trained or evaluated.", ""])
    return {"status": "blocked", "timestamp_count": len(timestamps), "date_range": [timestamps[0], timestamps[-1]] if timestamps else [], "independent_dates": len(dates), "labels": per_hazard, "missing_sources": missing_sources, "source_manifest": source_manifest, "ground_truth_contract": {"thunderstorm": "lightning or IMD report", "cloudburst": "independently verified rainfall observation; QPE/IMERG supporting only", "flash_flood": "Sentinel-1 flood extent, gauge, or authoritative disaster report"}, "split_feasibility": {"train": 0, "validation": 0, "test": 0, "feasible": False}, "required_additional_data": required, "markdown": "\n".join(lines)}


if __name__ == "__main__":
    main()
