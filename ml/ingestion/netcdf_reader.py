"""Metadata-only NetCDF inspection."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_netcdf(path: str | Path) -> dict[str, Any]:
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("xarray is required to inspect NetCDF products") from exc
    dataset = xr.open_dataset(path, decode_times=False)
    try:
        return {
            "format": "netcdf",
            "path": str(path),
            "dimensions": {str(k): int(v) for k, v in dataset.sizes.items()},
            "variables": {
                str(name): {"dimensions": list(variable.dims), "shape": list(variable.shape),
                            "dtype": str(variable.dtype), "attrs": {str(k): str(v) for k, v in variable.attrs.items()}}
                for name, variable in dataset.variables.items()
            },
            "attrs": {str(k): str(v) for k, v in dataset.attrs.items()},
        }
    finally:
        dataset.close()
