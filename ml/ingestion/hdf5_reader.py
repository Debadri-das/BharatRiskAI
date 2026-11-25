"""Metadata-only HDF5 inspection; arrays are never loaded during inspection."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_hdf5(path: str | Path) -> dict[str, Any]:
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError("h5py is required to inspect HDF5 products") from exc
    def describe(node: Any) -> dict[str, Any]:
        if isinstance(node, h5py.Dataset):
            return {
                "kind": "dataset", "shape": list(node.shape), "dtype": str(node.dtype),
                "attrs": {str(k): str(v) for k, v in node.attrs.items()},
            }
        return {"kind": "group", "children": sorted(node.keys()), "attrs": {str(k): str(v) for k, v in node.attrs.items()}}
    with h5py.File(path, "r") as handle:
        return {"format": "hdf5", "path": str(path), "members": {name: describe(handle[name]) for name in handle}}
