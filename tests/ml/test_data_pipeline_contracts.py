import numpy as np
import pytest

from reports.unified_feature_schema import CHANNEL_ORDER, GRID_CONTRACT, validate_channel_order
from scripts.calibration.calibrate import fit_temperature
from scripts.datasets.build_sequences import blocked_readiness
from scripts.preprocessing.align_datasets import jitter_and_gaps


def test_schema_order_and_grid_contract_are_explicit():
    assert len(CHANNEL_ORDER) == 13
    assert GRID_CONTRACT["shape"] == [114, 84]
    validate_channel_order(CHANNEL_ORDER)
    with pytest.raises(ValueError):
        validate_channel_order(CHANNEL_ORDER[:-1])


def test_sequence_readiness_keeps_unknown_and_invalid_labels_out_of_known_counts():
    report = blocked_readiness([
        {"hazard": "flash_flood", "timestamp": "2024-01-01T00:00:00+00:00", "label": None},
        {"hazard": "flash_flood", "timestamp": "2024-01-01T00:30:00+00:00", "label": "unknown"},
        {"hazard": "flash_flood", "timestamp": "2024-01-01T01:00:00+00:00", "label": 0},
    ])
    stats = report["labels"]["flash_flood"]
    assert stats["unknown"] == 1
    assert stats["invalid"] == 1
    assert stats["negative"] == 1
    assert stats["positive"] == 0
    assert report["status"] == "blocked"


def test_temporal_contract_reports_jitter_and_gaps_without_snapping():
    jitter, gaps = jitter_and_gaps([
        "2024-01-01T00:15:02+00:00",
        "2024-01-01T00:45:00+00:00",
        "2024-01-01T01:45:00+00:00",
    ])
    assert jitter[0]["offset_seconds_from_nominal_slot"] == 2.0
    assert gaps[0]["missing_slots"] == 1


def test_temperature_fit_rejects_unknown_or_non_binary_targets():
    with pytest.raises(ValueError):
        fit_temperature(np.array([0.1, 0.2]), np.array([0.0, np.nan]))
    with pytest.raises(ValueError):
        fit_temperature(np.array([0.1]), np.array([2.0]))
