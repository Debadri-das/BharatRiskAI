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
    """Discover timestamped, canonical-channel feature grids deterministically."""
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


def _find_stamp(expected: datetime, pool: dict[datetime, Path], max_sec: int = 120) -> datetime | None:
    if expected in pool:
        return expected
    for s in pool:
        if abs((s - expected).total_seconds()) <= max_sec:
            return s
    return None


def _find_label(target_time: datetime, hazard: str, lookup: dict[tuple[datetime, str], Path], max_sec: int = 120) -> Path | None:
    if (target_time, hazard) in lookup:
        return lookup[(target_time, hazard)]
    for (stamp, h), p in lookup.items():
        if h == hazard and abs((stamp - target_time).total_seconds()) <= max_sec:
            return p
    return None


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
    samples: list[dict[str, Any]] = []

    for anchor in stamps:
        input_times = [_find_stamp(anchor - interval * offset, grids) for offset in range(INPUT_FRAME_COUNT - 1, -1, -1)]
        target_times = [anchor + interval * offset for offset in TARGET_HORIZON_OFFSETS]
        if any(stamp is None for stamp in input_times):
            continue

        inputs: list[np.ndarray] = []
        for stamp in input_times:
            with np.load(grids[stamp], allow_pickle=False) as data:
                inputs.append(np.stack([np.asarray(data[name], dtype=np.float32) for name in CHANNEL_ORDER]))
        input_array = np.stack(inputs)

        target_layers: list[np.ndarray] = []
        for target_time in target_times:
            hazard_layers: list[np.ndarray] = []
            for hazard in HAZARDS:
                path = _find_label(target_time, hazard, label_lookup)
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

    default_features = ROOT / "data" / "derived" / "unified" if (ROOT / "data" / "derived" / "unified").exists() else ROOT / "data" / "derived" / "satellite"
    parser = argparse.ArgumentParser(description="Build canonical 7-frame, +2h..+6h sequences")
    parser.add_argument("--features", type=Path, default=default_features)
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
    train_dates = {dates[0]}  # 2020-05-20 (Amphan)
    validation_dates = {dates[1]}  # 2021-05-26 (Yaas)
    test_dates = {dates[2]}  # 2024-05-26 (Remal)

    for row in samples:
        if row["event_id"] in train_dates:
            row["split"] = "train"
        elif row["event_id"] in validation_dates:
            row["split"] = "validation"
        else:
            row["split"] = "test"

    # Write split CSVs
    for name, split_dates in [("train", train_dates), ("validation", validation_dates), ("test", test_dates)]:
        split_samples = [r for r in samples if r["event_id"] in split_dates]
        with (split_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for r in split_samples:
                writer.writerow({
                    "event_id": r["event_id"],
                    "timestamp": r["timestamp"],
                    "spatial_tile": "kolkata",
                    "input_sequence": r["input_path"],
                    "target_sequence": r["target_path"],
                    "hazard_labels": "thunderstorm,cloudburst,flash_flood",
                    "split": name,
                })

    final_dir = ROOT / "data" / "datasets" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    with (final_dir / "index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=samples[0].keys())
        writer.writeheader()
        writer.writerows(samples)
    print(f"Sequence stage complete: created {len(samples)} samples across {len(dates)} event dates: train={len([s for s in samples if s['split']=='train'])}, val={len([s for s in samples if s['split']=='validation'])}, test={len([s for s in samples if s['split']=='test'])}")


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
        "INSAT-3DR L1C imager granules for at least 3+ independent dates covering real weather events.",
        "Contemporaneous INSAT QPE (HEM) for those same dates.",
        "IMDAA pressure-level profiles.",
        "At least one authoritative thunderstorm/lightning observation source.",
        "An authoritative cloudburst definition/threshold.",
        "Official flood/inundation observations.",
        "Optional: INSAT CMV products.",
    ]
    lines = [
        "# Data readiness", "",
        "## Status", "",
        f"Blocked for supervised training: {sum(v['unknown'] for v in per_hazard.values())} targets unknown.", "",
        f"- Timestamp count: {len(timestamps)}",
        f"- Independent dates: {len(dates)}",
    ]
    return {
        "status": "blocked",
        "timestamp_count": len(timestamps),
        "independent_dates": len(dates),
        "labels": per_hazard,
        "missing_sources": missing_sources,
        "source_manifest": source_manifest,
        "required_additional_data": required,
        "markdown": "\n".join(lines),
    }


if __name__ == "__main__":
    main()
