"""Resumable, metadata-first batch ingestion CLI.

This command registers source files and writes provenance manifests. It does not
download data or invent values when a source is absent.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import yaml

from .base import write_json
from .file_registry import FileRegistry
from .grib_reader import inspect_grib
from .hdf5_reader import inspect_hdf5
from .netcdf_reader import inspect_netcdf


FORMATS = {".h5": inspect_hdf5, ".hdf5": inspect_hdf5, ".nc": inspect_netcdf, ".nc4": inspect_netcdf, ".netcdf": inspect_netcdf, ".grib": inspect_grib, ".grb": inspect_grib}


def product_for(path: Path) -> str:
    name = str(path).lower()
    if "qpe" in name or "hem" in name:
        return "insat_qpe"
    if "cmv" in name:
        return "insat_cmv"
    if "imdaa" in name or "grib" in name:
        return "imdaa"
    if "dem" in name or "elev" in name or path.suffix.lower() in {".tif", ".tiff"}:
        return "dem"
    return "insat_l1c"


def discover(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in set(FORMATS) | {".tif", ".tiff", ".npz"})


def run(config: Path, source: str | None = None, inspect: bool = False) -> dict[str, Any]:
    settings = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    root = Path(settings.get("data_root", "."))
    registry = FileRegistry(root / "data" / "reports" / "file_registry.json")
    records = []
    for path in discover(root / "data"):
        product = product_for(path)
        if source and source not in product:
            continue
        record = registry.register(path, product)
        if inspect and record.readable and path.suffix.lower() in FORMATS:
            try:
                record = registry.register(path, product, inspected=FORMATS[path.suffix.lower()](path))
            except (OSError, RuntimeError, ValueError) as exc:
                record = registry.register(path, product, inspection_error=str(exc))
        records.append(record.as_dict())
    registry.save()
    report = {"files": records, "duplicates": registry.duplicate_hashes(), "accepted": sum(r["status"] == "ACCEPTED" for r in records), "rejected": sum(r["status"] == "REJECTED" for r in records)}
    write_json(root / "data" / "reports" / "ingestion_manifest.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/data.yaml"))
    parser.add_argument("--source", choices=["insat_l1c", "insat_qpe", "insat_cmv", "imdaa", "dem"])
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    print(run(args.config, None if args.all else args.source, args.inspect))


if __name__ == "__main__":
    main()
