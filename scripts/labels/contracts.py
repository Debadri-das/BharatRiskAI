"""Ground-truth label contracts and deterministic filesystem adapters.

This module deliberately does not download or infer observations.  Predictor
products (including QPE and IMERG) are inputs to the model, not ground truth.
Only records backed by an independently observed source may be ``confirmed``.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
SOURCE_CONTRACT = {
    "thunderstorm": {"lightning", "imd_report"},
    "cloudburst": {"rain_gauge", "imd_report", "authoritative_rainfall_report"},
    "flash_flood": {"sentinel1_flood_extent", "gauge", "disaster_report"},
}
PREDICTOR_ONLY = {"qpe", "insat_qpe", "imerg", "satellite_signature", "terrain_risk"}


class LabelContractError(ValueError):
    """A label cannot be accepted as ground truth."""


def validate_ground_truth(record: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one observed-label record.

    Required fields are intentionally small so CSV and JSONL exports can be
    prepared without a service account. ``label`` is binary or null (unknown).
    A source must be authoritative for the hazard; QPE/IMERG can be listed in
    ``supporting_sources`` but can never make a record confirmed.
    """
    required = {"hazard", "timestamp", "label", "source_type"}
    missing = sorted(required - record.keys())
    if missing:
        raise LabelContractError(f"missing required fields: {missing}")
    hazard = record["hazard"]
    if hazard not in HAZARDS:
        raise LabelContractError(f"unsupported hazard: {hazard!r}")
    source = str(record["source_type"]).lower().strip()
    if source in PREDICTOR_ONLY or source not in SOURCE_CONTRACT[hazard]:
        raise LabelContractError(
            f"{source!r} is not an authoritative {hazard} source; "
            "predictor/QPE evidence cannot be ground truth"
        )
    label = record["label"]
    if isinstance(label, str):
        if label.strip().lower() in {"", "null", "unknown", "none"}:
            label = None
        elif label.strip() in {"0", "0.0", "false", "False"}:
            label = 0
        elif label.strip() in {"1", "1.0", "true", "True"}:
            label = 1
    if label is not None and label not in (0, 1, False, True, 0.0, 1.0):
        raise LabelContractError("label must be 0, 1, or null")
    if not record["timestamp"]:
        raise LabelContractError("timestamp is required")
    normalized = dict(record)
    normalized.update({
        "hazard": hazard,
        "source_type": source,
        "label": None if label is None else int(bool(label)),
        "label_type": "confirmed" if label is not None else "unknown",
        "ground_truth": True,
    })
    normalized.setdefault("supporting_sources", [])
    return normalized


def load_filesystem_observations(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load deterministic JSONL/CSV observations from ``root``.

    No network or credentials are used. Invalid files are reported as blocked
    reasons rather than silently becoming proxy labels.
    """
    records: list[dict[str, Any]] = []
    blocked: list[str] = []
    if not root.exists():
        return records, [f"missing observation directory: {root}"]
    paths = sorted(p for p in root.rglob("*") if p.suffix.lower() in {".jsonl", ".csv"})
    for path in paths:
        try:
            if path.suffix.lower() == ".jsonl":
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
            for row_number, row in enumerate(rows, 1):
                try:
                    records.append(validate_ground_truth(row))
                except (LabelContractError, TypeError) as exc:
                    blocked.append(f"{path}:{row_number}: {exc}")
        except (OSError, json.JSONDecodeError, csv.Error) as exc:
            blocked.append(f"{path}: {exc}")
    return records, blocked


def readiness(root: Path) -> dict[str, Any]:
    """Return explicit availability/blocking status for local observations."""
    records, blocked = load_filesystem_observations(root)
    by_hazard = {hazard: sum(r["hazard"] == hazard for r in records) for hazard in HAZARDS}
    missing = [f"authoritative {hazard} observations" for hazard, count in by_hazard.items() if not count]
    return {"status": "ready" if records and not blocked and not missing else "blocked",
            "records": len(records), "by_hazard": by_hazard,
            "blocked": blocked, "missing": missing,
            "note": "QPE/IMERG are supporting evidence only and cannot satisfy any missing contract."}
