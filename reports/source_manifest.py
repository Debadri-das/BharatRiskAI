"""Local, non-mutating readiness checks for the Tier-1/2 source manifest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config" / "source_manifest.json"
VALID_STATUSES = {"available", "missing", "optional"}


def load_source_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load the repository contract; this does not access a network or create files."""
    return json.loads(path.read_text(encoding="utf-8"))


def _path_has_data(root: Path, pattern: str) -> bool:
    # A directory itself is not evidence of a source. Require at least one file.
    exact = root / pattern
    if exact.is_dir():
        return any(path.is_file() for path in exact.rglob("*"))
    matches = (root / pattern).glob("*") if pattern.endswith("/") else root.glob(pattern)
    return any(path.is_file() for path in matches)


def source_readiness(root: Path = ROOT, manifest_path: Path = MANIFEST_PATH) -> dict[str, dict[str, Any]]:
    """Return one status per manifest source without downloading or fabricating data."""
    manifest = load_source_manifest(manifest_path)
    result: dict[str, dict[str, Any]] = {}
    for source in manifest["sources"]:
        available = any(_path_has_data(root, pattern) for pattern in source["paths"])
        status = "available" if available else ("missing" if source["required"] else "optional")
        result[source["id"]] = {
            "name": source["name"],
            "tier": source["tier"],
            "role": source["role"],
            "required": source["required"],
            "status": status,
            "available": available,
            "paths": source["paths"],
        }
    return result


def manifest_summary(root: Path = ROOT, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    sources = source_readiness(root, manifest_path)
    return {
        "sources": sources,
        "missing_required": [item["name"] for item in sources.values() if item["status"] == "missing"],
        "optional_unavailable": [item["name"] for item in sources.values() if item["status"] == "optional"],
        "available": [item["name"] for item in sources.values() if item["status"] == "available"],
    }
