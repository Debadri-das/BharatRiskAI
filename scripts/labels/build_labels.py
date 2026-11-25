"""Build labels only from supplied authoritative observations.

This command intentionally refuses to manufacture spatial labels or to treat
satellite QPE/signatures as confirmed ground truth. Use
``ml.preprocessing.proxy_target_builder`` for the separately versioned future
observation proxy target.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json

from scripts.labels.contracts import load_filesystem_observations, validate_ground_truth


def build(source_dir: str | Path, output: str | Path) -> dict:
    records, blocked = load_filesystem_observations(Path(source_dir))
    validated = [validate_ground_truth(item) for item in records]
    if not validated:
        raise ValueError("No authoritative observations supplied; confirmed labels cannot be fabricated")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(json.dumps(item) for item in validated) + "\n", encoding="utf-8")
    return {"accepted": len(validated), "blocked": len(blocked), "output": str(destination)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build confirmed labels from user-supplied observations")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
