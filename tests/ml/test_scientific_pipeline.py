from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from ml.preprocessing.proxy_target_builder import ProxyTargetConfig, build_future_qpe_targets
from ml.preprocessing.qpe import accumulate_rate


def test_qpe_rate_is_integrated_over_real_intervals_and_preserves_nan():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=30 * index) for index in range(3)]
    result = accumulate_rate(np.array([[2.0], [4.0], [np.nan]]), times, 1.0)
    assert np.isnan(result.value[0])
    assert result.status == "INSUFFICIENT_COVERAGE"

    result = accumulate_rate(np.array([[2.0], [4.0], [6.0]]), times, 1.0)
    assert result.value[0] == pytest.approx(5.0)
    assert result.coverage[0] == pytest.approx(1.0)


def test_proxy_target_excludes_incomplete_future_coverage():
    issue = pd.Timestamp("2024-01-01T00:00:00Z")
    frame = pd.DataFrame(
        {
            "issue_time": [issue, issue, issue + pd.Timedelta(hours=1)],
            "qpe_time": [issue + pd.Timedelta(hours=3), issue + pd.Timedelta(hours=6), issue + pd.Timedelta(hours=3)],
            "qpe_accumulation_mm": [60.0, np.nan, 10.0],
        }
    )
    targets = build_future_qpe_targets(frame, ProxyTargetConfig())
    assert targets.iloc[0]["target_status"] == "UNUSABLE_MISSING_FUTURE"
    assert np.isnan(targets.iloc[0]["target"])
    assert targets.iloc[1]["target"] == 0
    assert targets.iloc[1]["target_type"] == "binary_proxy"
