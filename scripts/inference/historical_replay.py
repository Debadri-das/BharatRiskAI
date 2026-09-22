"""Replay a historical timestamp only when a trained checkpoint and labels exist."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="UTC timestamp, for example 20230701_0015")
    parser.parse_args()
    missing: list[str] = []
    if not (ROOT / "models" / "checkpoints" / "best.pt").exists():
        missing.append("trained checkpoint (models/checkpoints/best.pt)")
    if not (ROOT / "models" / "calibration" / "temperature.json").exists():
        missing.append("calibration parameters (models/calibration/temperature.json)")
    labels_path = ROOT / "data" / "datasets" / "labels" / "labels.jsonl"
    has_observed_labels = False
    if labels_path.exists():
        import json
        for line in labels_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if record.get("label") is not None and record.get("label_type") == "confirmed":
                    has_observed_labels = True
                    break
    if not has_observed_labels:
        missing.append("observed (confirmed) spatial labels - current labels are proxies or unknown and must never be replayed as ground truth")
    if missing:
        raise RuntimeError("Replay blocked, missing prerequisites: " + "; ".join(missing))
    raise RuntimeError("Replay prerequisites found; visualization rendering is not implemented for this dataset yet.")


if __name__ == "__main__":
    main()
