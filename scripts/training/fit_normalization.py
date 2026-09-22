"""Fit feature normalization using training samples only."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    index = ROOT / "data" / "datasets" / "final" / "index.csv"
    if not index.exists():
        raise RuntimeError("Normalization blocked: final event-split index is missing.")
    with index.open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["split"] == "train"]
    if not rows:
        raise RuntimeError("Normalization blocked: training split is empty.")
    arrays = [np.load(ROOT / row["input_path"], allow_pickle=False)["inputs"] for row in rows]
    values = np.concatenate([array.reshape(array.shape[0], array.shape[1], -1).transpose(1, 0, 2).reshape(array.shape[1], -1) for array in arrays], axis=1)
    if not np.isfinite(values).all():
        raise RuntimeError("Normalization blocked: training data contains missing values; resolve masks before fitting statistics.")
    stats = {"method": "training-only per-channel standardization", "channels": [{"mean": float(values[index].mean()), "std": float(max(values[index].std(), 1e-8))} for index in range(values.shape[0])]}
    output = ROOT / "models" / "preprocessing" / "scaler.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(stats, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
