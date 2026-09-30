import json

from reports.source_manifest import manifest_summary, source_readiness
from scripts.datasets.build_sequences import blocked_readiness


def test_manifest_names_tier_one_and_optional_sources():
    report = manifest_summary()
    names = {item["name"] for item in report["sources"].values()}
    assert {"INSAT-3DR WV", "INSAT-3DR TIR", "INSAT-3DR QPE", "IMDAA", "SRTM/NASADEM"} <= names
    assert {"CMV", "IMERG", "IMD", "Lightning", "Sentinel-1", "Land cover", "Soil moisture", "ERA5"} <= names
    assert all(item["status"] in {"available", "missing", "optional"} for item in report["sources"].values())


def test_readiness_is_filesystem_only_and_distinguishes_required_and_optional(tmp_path):
    manifest = {
        "sources": [
            {"id": "required", "name": "Required", "tier": 1, "role": "baseline", "required": True, "paths": ["data/base/**/*"]},
            {"id": "optional", "name": "Optional", "tier": 2, "role": "enhancement", "required": False, "paths": ["data/extra/**/*"]},
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "data" / "base").mkdir(parents=True)
    (tmp_path / "data" / "base" / "sample.bin").write_bytes(b"local")

    statuses = source_readiness(tmp_path, manifest_path)
    assert statuses["required"]["status"] == "available"
    assert statuses["optional"]["status"] == "optional"
    assert not (tmp_path / "data" / "extra").exists()


def test_sequence_readiness_embeds_source_manifest_statuses():
    report = blocked_readiness([])
    assert "source_manifest" in report
    assert report["source_manifest"]["sources"]["imdaa"]["status"] == "missing"
    assert report["source_manifest"]["sources"]["cmv"]["status"] == "optional"
