"""Run BharatRiskAI data and ML stages reproducibly on Windows."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    "audit": ["scripts/audit_dataset.py"],
    "extract": ["scripts/insat/extract_l1c.py"],
    "features": ["scripts/features/satellite_features.py", "scripts/features/qpe_features.py", "scripts/features/dem_features.py", "scripts/features/build_unified_features.py"],
    "align": ["scripts/preprocessing/align_datasets.py"],
    "labels": ["scripts/labels/build_labels.py"],
    "split": ["scripts/datasets/build_sequences.py"],
    "sequence": ["scripts/datasets/build_sequences.py"],
    "validate": ["scripts/validation/validate_dataset.py"],
    "normalize": ["scripts/training/fit_normalization.py"],
    "train": ["scripts/training/train_multitask.py --epochs 100 --patience 15 --amp"],
    "calibrate": ["scripts/calibration/calibrate.py"],
    "thresholds": ["scripts/calibration/select_thresholds.py"],
    "evaluate": ["scripts/evaluation/evaluate.py"],
}


import os


def run(script_cmd: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    parts = script_cmd.split()
    script = parts[0]
    extra_args = parts[1:]
    command = [sys.executable, str(ROOT / script), *extra_args]
    print("RUN", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=[*STAGES, "all"])
    args = parser.parse_args()
    stages = list(STAGES) if args.stage == "all" else [args.stage]
    completed: set[str] = set()
    for stage in stages:
        if stage in completed:
            continue
        for script in STAGES[stage]:
            run(script)
        completed.add(stage)


if __name__ == "__main__":
    main()
