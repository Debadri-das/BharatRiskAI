"""Idempotent local registry for scientific source files."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
from typing import Any

from .base import FileMetadata, sha256_file, utc_timestamp


class FileRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            self.records = json.loads(self.path.read_text(encoding="utf-8"))

    def register(self, file_path: str | Path, product: str, **metadata: Any) -> FileMetadata:
        source = Path(file_path)
        try:
            digest = sha256_file(source)
            record = FileMetadata(
                path=str(source),
                product=product,
                format=source.suffix.lower().lstrip("."),
                size_bytes=source.stat().st_size,
                sha256=digest,
                modified_at=utc_timestamp(datetime.fromtimestamp(source.stat().st_mtime)),
                readable=True,
                status="ACCEPTED",
                metadata=metadata or None,
            )
        except (OSError, ValueError) as exc:
            record = FileMetadata(
                path=str(source), product=product, format=source.suffix.lower().lstrip("."),
                size_bytes=source.stat().st_size if source.exists() else 0,
                sha256="", modified_at="", readable=False, status="REJECTED", error=str(exc),
            )
        self.records[record.sha256 or record.path] = record.as_dict()
        return record

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.records, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def duplicate_hashes(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for record in self.records.values():
            digest = record.get("sha256")
            if digest:
                grouped.setdefault(digest, []).append(record["path"])
        return {key: paths for key, paths in grouped.items() if len(paths) > 1}
