"""Metadata-only GRIB inspection with an actionable optional dependency error."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_grib(path: str | Path) -> dict[str, Any]:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("xarray is required to inspect GRIB products") from exc
    try:
        dataset = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    except Exception as exc:
        raise ValueError(f"Unable to decode GRIB metadata for {path}: {exc}") from exc
    try:
        return {
            "format": "grib",
            "path": str(path),
            "dimensions": {str(k): int(v) for k, v in dataset.sizes.items()},
            "variables": {str(name): {"dimensions": list(var.dims), "shape": list(var.shape), "attrs": dict(var.attrs)} for name, var in dataset.data_vars.items()},
            "attrs": dict(dataset.attrs),
        }
    finally:
        dataset.close()
