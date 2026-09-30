from pathlib import Path

import pytest

from scripts.labels.contracts import LabelContractError, load_filesystem_observations, readiness, validate_ground_truth


def test_qpe_and_imerg_can_never_be_confirmed_truth():
    for source in ("qpe", "imerg"):
        with pytest.raises(LabelContractError, match="cannot be ground truth"):
            validate_ground_truth({"hazard": "flash_flood", "timestamp": "2024-01-01T00:00:00Z", "label": 1, "source_type": source})


def test_each_hazard_has_explicit_authoritative_source_contract():
    assert validate_ground_truth({"hazard": "thunderstorm", "timestamp": "2024-01-01T00:00:00Z", "label": 1, "source_type": "lightning"})["label_type"] == "confirmed"
    assert validate_ground_truth({"hazard": "cloudburst", "timestamp": "2024-01-01T00:00:00Z", "label": "0", "source_type": "rain_gauge"})["label"] == 0
    assert validate_ground_truth({"hazard": "flash_flood", "timestamp": "2024-01-01T00:00:00Z", "label": 1, "source_type": "sentinel1_flood_extent"})["ground_truth"] is True


def test_filesystem_adapter_is_deterministic_and_reports_invalid_rows(tmp_path: Path):
    path = tmp_path / "observations.jsonl"
    path.write_text(
        '{"hazard":"flash_flood","timestamp":"2024-01-01T00:00:00Z","label":1,"source_type":"gauge"}\n'
        '{"hazard":"flash_flood","timestamp":"2024-01-01T00:30:00Z","label":1,"source_type":"qpe"}\n',
        encoding="utf-8",
    )
    records, blocked = load_filesystem_observations(tmp_path)
    assert len(records) == 1
    assert len(blocked) == 1
    assert readiness(tmp_path)["status"] == "blocked"
