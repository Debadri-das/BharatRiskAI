from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from reports.unified_feature_schema import CHANNEL_ORDER
from scripts.datasets.build_sequences import assemble_sequences


def _features(root: Path, shape=(2, 3), count=7):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        stamp = start + timedelta(minutes=30 * index)
        np.savez(
            root / f"frame_{index}.npz",
            timestamp=stamp.isoformat(),
            **{name: np.full(shape, index, dtype=np.float32) for name in CHANNEL_ORDER},
        )
    return start + timedelta(minutes=30 * (count - 1))


def _labels(root: Path, anchor: datetime, shape=(2, 3), label=0):
    rows = []
    for offset in (4, 6, 8, 10, 12):
        stamp = anchor + timedelta(minutes=30 * offset)
        for hazard in ("thunderstorm", "cloudburst", "flash_flood"):
            path = root / f"{hazard}_{offset}.npy"
            np.save(path, np.full(shape, label, dtype=np.float32))
            rows.append({"timestamp": stamp.isoformat(), "hazard": hazard, "label": label, "label_grid_path": path.name, "label_type": "confirmed"})
    return rows


def test_assembles_canonical_shapes_and_preserves_grid_values(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    anchor = _features(features)
    labels = _labels(tmp_path, anchor)

    samples = assemble_sequences(features, labels, label_root=tmp_path)

    assert len(samples) == 1
    assert samples[0]["inputs"].shape == (7, 13, 2, 3)
    assert samples[0]["targets"].shape == (5, 3, 2, 3)
    assert np.all(samples[0]["inputs"][0] == 0)
    assert np.all(samples[0]["targets"] == 0)


def test_missing_cadence_does_not_get_fabricated(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    anchor = _features(features)
    (features / "frame_3.npz").unlink()
    with pytest.raises(ValueError, match="No valid"):
        assemble_sequences(features, _labels(tmp_path, anchor), label_root=tmp_path)


def test_unknown_label_is_blocked(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    anchor = _features(features)
    labels = _labels(tmp_path, anchor)
    labels[0]["label"] = None
    with pytest.raises(ValueError, match="Unknown or invalid"):
        assemble_sequences(features, labels, label_root=tmp_path)


def test_shape_mismatch_is_blocked(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    anchor = _features(features)
    mismatch = features / "frame_bad.npz"
    np.savez(mismatch, timestamp=(anchor + timedelta(minutes=30)).isoformat(), **{name: np.zeros((4, 3), dtype=np.float32) for name in CHANNEL_ORDER})
    with pytest.raises(ValueError, match="inconsistent spatial shapes"):
        assemble_sequences(features, _labels(tmp_path, anchor), label_root=tmp_path)
