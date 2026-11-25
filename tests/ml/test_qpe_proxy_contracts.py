from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ml.preprocessing.proxy_target_builder import (
    ProxyTargetConfig,
    assert_future_only,
    build_future_qpe_targets,
)
from ml.preprocessing.qpe import accumulate_rate


def test_qpe_accumulation_preserves_missing_intervals():
    start = datetime(2020, 4, 1, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=30 * index) for index in range(7)]
    rates = np.array([[[1.0]], [[1.0]], [[np.nan]], [[1.0]], [[1.0]], [[1.0]], [[1.0]]])
    result = accumulate_rate(rates, times, 3.0)
    assert np.isnan(result.value).all()
    assert result.coverage.item() < 0.9


def test_proxy_targets_group_by_timestamp_and_grid_cell():
    issue = pd.Timestamp("2020-04-01T00:00:00Z")
    frame = pd.DataFrame(
        [
            {"issue_time": issue, "grid_id": "a", "qpe_time": issue + pd.Timedelta(hours=3), "qpe_accumulation_mm": 60},
            {"issue_time": issue, "grid_id": "b", "qpe_time": issue + pd.Timedelta(hours=3), "qpe_accumulation_mm": 10},
        ]
    )
    targets = build_future_qpe_targets(frame, ProxyTargetConfig())
    assert set(targets["grid_id"]) == {"a", "b"}
    assert targets.set_index("grid_id").loc["a", "target"] == 1
    assert targets.set_index("grid_id").loc["b", "target"] == 0


def test_proxy_composite_key_allows_multiple_cells_at_same_issue_time():
    frame = pd.DataFrame(
        [
            {"issue_time": "2020-04-01T00:00:00Z", "grid_id": "a"},
            {"issue_time": "2020-04-01T00:00:00Z", "grid_id": "b"},
        ]
    )
    assert_future_only(frame, frame)
