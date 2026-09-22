"""Align downloaded INSAT products to the Kolkata DEM grid and write processed NPZ files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion.real_data import align_to_grid, read_insat, read_qpe, target_grid

ROOT = Path(__file__).resolve().parents[1]
DEM = ROOT / "data" / "dem" / "kolkata_dem.tif"
INSAT_RAW = ROOT / "data" / "insat"


def main() -> None:
    grid = target_grid(DEM)
    previous_ctt = None
    previous_time = None
    for path in sorted(INSAT_RAW.rglob("*.h5")):
        if "processed" in path.parts:
            continue
        try:
            product = read_qpe(path) if "qpe" in path.parts else read_insat(path)
        except (KeyError, ValueError):
            continue
        output = {"observed_at": product["observed_at"]}
        for variable in ("ctt", "wv_bt", "qpe"):
            if variable in product:
                output[variable] = align_to_grid(product[variable], product["latitude"], product["longitude"], grid, nearest=variable == "qpe")
        if len(output) == 1:
            continue
        product_dir = path.parent.parent if path.parent.name == "raw" else path.parent
        processed = product_dir / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        if "ctt" in output and previous_ctt is not None:
            elapsed_hours = max((np.datetime64(output["observed_at"]) - np.datetime64(previous_time)) / np.timedelta64(1, "h"), 1 / 60)
            output["ctt_cooling_rate"] = -(output["ctt"] - previous_ctt) / elapsed_hours
        if "ctt" in output:
            previous_ctt = output["ctt"]
            previous_time = output["observed_at"]
        target = processed / f"{path.stem}.npz"
        np.savez_compressed(target, **output)
        target.with_suffix(".json").write_text(json.dumps({"source": str(path), "grid_shape": list(grid["shape"]), "crs": str(grid["crs"])}, indent=2), encoding="utf-8")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
