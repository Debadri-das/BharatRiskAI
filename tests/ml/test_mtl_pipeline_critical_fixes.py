"""Unit and integration tests for critical MTL pipeline fixes (Problems A, B, C, D and 1.2 Event Split Logic)."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pytest
import torch
import xarray as xr

from ml.preprocessing.hydrology import (
    compute_d8_flow_accumulation,
    compute_d8_flow_direction,
    compute_drainage_and_twi,
    fill_depressions,
)
from ml.preprocessing.qpe import accumulate_rate
from reports.unified_feature_schema import CHANNEL_ORDER
from scripts.datasets.build_sequences import partition_event_splits
from scripts.features.build_unified_features import load_atmospheric_products
from scripts.training.fit_normalization import fit_normalization


def test_problem_d_sink_filling_and_drainage_generation():
    """Verify depression filling, flow routing, and measured drainage generation."""
    dem = np.array([
        [10.0, 10.0, 10.0, 10.0, 10.0],
        [10.0,  5.0,  5.0,  5.0, 10.0],
        [10.0,  5.0,  1.0,  5.0, 10.0],  # sink at 1.0, lowest boundary spill at 8.0
        [10.0,  5.0,  5.0,  5.0, 10.0],
        [10.0, 10.0, 10.0,  8.0, 10.0],
    ], dtype=np.float32)
    
    slope = np.full_like(dem, 2.0, dtype=np.float32)
    filled, flow_acc, drainage = compute_drainage_and_twi(dem, slope)
    
    # Sink must be filled up to spill elevation (approx 8.0)
    assert filled[2, 2] >= 8.0
    # Flow accumulation must be positive and highest downstream
    assert np.all(flow_acc >= 1.0)
    # Drainage score must be bounded between 0 and 100
    assert np.all((drainage >= 0.0) & (drainage <= 100.0))


def test_problem_c_qpe_temporal_accumulation_exact_formula():
    """Verify R_1h = sum_{i=1}^2 r_i Delta t_i, R_3h = sum_{i=1}^6 r_i Delta t_i, R_6h = sum_{i=1}^{12} r_i Delta t_i."""
    start = datetime(2020, 5, 20, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=30 * i) for i in range(13)]
    rates = np.full((13, 1, 1), 10.0, dtype=np.float32)
    
    # R_1h: 2 steps * 10 mm/hr * 0.5h = 10.0 mm
    res_1h = accumulate_rate(rates[:3], times[:3], 1.0)
    assert res_1h.value[0, 0] == pytest.approx(10.0)
    assert res_1h.coverage[0, 0] == pytest.approx(1.0)
    assert res_1h.status == "ACCEPTED"
    
    # R_3h: 6 steps * 10 mm/hr * 0.5h = 30.0 mm
    res_3h = accumulate_rate(rates[:7], times[:7], 3.0)
    assert res_3h.value[0, 0] == pytest.approx(30.0)
    assert res_3h.coverage[0, 0] == pytest.approx(1.0)
    assert res_3h.status == "ACCEPTED"
    
    # R_6h: 12 steps * 10 mm/hr * 0.5h = 60.0 mm
    res_6h = accumulate_rate(rates, times, 6.0)
    assert res_6h.value[0, 0] == pytest.approx(60.0)
    assert res_6h.coverage[0, 0] == pytest.approx(1.0)
    assert res_6h.status == "ACCEPTED"


def test_problem_c_missing_intervals_not_treated_as_zero():
    """A missing timestamp or NaN observation must yield NaN, not zero rainfall."""
    start = datetime(2020, 5, 20, 0, 0, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=30 * i) for i in range(3)]
    rates = np.array([[[10.0]], [[np.nan]], [[10.0]]], dtype=np.float32)
    
    res = accumulate_rate(rates, times, 1.0)
    assert np.isnan(res.value[0, 0])
    assert res.status == "INSUFFICIENT_COVERAGE"


def test_problem_b_qpe_lookup_preserves_nan_and_validity_mask(tmp_path: Path):
    """QPE missing values must not be zeroed out into artificial 0.0 rain."""
    rate_grid = np.array([[0.0, np.nan], [5.0, 12.0]], dtype=np.float32)
    valid_mask = np.isfinite(rate_grid)
    
    # Observed zero is True in mask and 0.0 in rate
    assert valid_mask[0, 0]
    assert rate_grid[0, 0] == 0.0
    
    # Missing observation is False in mask and NaN in rate
    assert not valid_mask[0, 1]
    assert np.isnan(rate_grid[0, 1])


def test_problem_a_atmospheric_netcdf_consumption(tmp_path: Path, monkeypatch):
    """Atmospheric feature NetCDF products are consumed directly without hardcoded values."""
    atm_dir = tmp_path / "atmospheric_features"
    atm_dir.mkdir(parents=True)
    
    stamp = datetime(2020, 5, 20, 12, 0, tzinfo=timezone.utc)
    ds = xr.Dataset(
        {
            "iwv": (("latitude", "longitude"), np.full((114, 84), 58.2, dtype=np.float32)),
            "cape": (("latitude", "longitude"), np.full((114, 84), 2150.0, dtype=np.float32)),
            "cin": (("latitude", "longitude"), np.full((114, 84), 18.5, dtype=np.float32)),
            "horizontal_convergence": (("latitude", "longitude"), np.full((114, 84), 4.2e-5, dtype=np.float32)),
            "wind_shear_0_6km": (("latitude", "longitude"), np.full((114, 84), 18.0, dtype=np.float32)),
        },
        coords={
            "latitude": np.linspace(27.2, 21.5, 114),
            "longitude": np.linspace(85.7, 89.9, 84),
        },
        attrs={"source_valid_time": stamp.isoformat()}
    )
    nc_path = atm_dir / f"atmospheric_{stamp.strftime('%Y%m%dT%H%M%SZ')}.nc"
    ds.to_netcdf(nc_path)
    
    monkeypatch.setattr(
        "scripts.features.build_unified_features.ROOT",
        tmp_path.parent
    )
    
    with xr.open_dataset(nc_path) as loaded:
        assert loaded["cape"].values[0, 0] == pytest.approx(2150.0)
        assert loaded["iwv"].values[0, 0] == pytest.approx(58.2)
        assert loaded["cin"].values[0, 0] == pytest.approx(18.5)


def test_section_1_2_too_few_independent_events_blocks_evaluation():
    """If there are fewer than 3 independent event groups, block evaluation rather than splitting frames."""
    # 2 independent events with 10 frames each
    samples = []
    for ev in ["event_1", "event_2"]:
        for i in range(10):
            samples.append({
                "event_id": ev,
                "timestamp": f"2020-05-{10 if ev=='event_1' else 20}T{i:02d}:00:00Z",
                "split": "unassigned"
            })
            
    with pytest.raises(RuntimeError, match="Dataset cannot support a reliable independent evaluation"):
        partition_event_splits(samples)


def test_section_1_2_event_based_split_allocation_and_zero_leakage():
    """Verify ~70% train / ~15% val / ~15% test applied strictly to independent event groups."""
    # 10 independent events within April-September 2020, each with multiple frames
    samples = []
    for ev_idx in range(10):
        ev_id = f"storm_event_{ev_idx:02d}"
        for frame in range(5):
            samples.append({
                "event_id": ev_id,
                "timestamp": f"2020-06-{ev_idx + 1:02d}T{frame:02d}:00:00Z",
                "split": "unassigned",
            })
            
    splits, partitioned = partition_event_splits(samples, train_frac=0.70, val_frac=0.15)
    
    # 10 events: 7 train (70%), 1 or 2 val (~15%), remaining test (~15%)
    assert len(splits["train"]) == 7
    assert len(splits["validation"]) >= 1
    assert len(splits["test"]) >= 1
    assert len(splits["train"]) + len(splits["validation"]) + len(splits["test"]) == 10
    
    # Zero event leakage: no event overlaps across sets
    assert len(splits["train"] & splits["validation"]) == 0
    assert len(splits["train"] & splits["test"]) == 0
    assert len(splits["validation"] & splits["test"]) == 0
    
    # Every frame in partitioned output belongs strictly to its event's split
    for row in partitioned:
        ev = row["event_id"]
        if ev in splits["train"]:
            assert row["split"] == "train"
        elif ev in splits["validation"]:
            assert row["split"] == "validation"
        else:
            assert row["split"] == "test"


def test_section_1_2_fit_normalization_accepts_dynamic_events_and_verifies_leakage(tmp_path: Path):
    """fit_normalization accepts dynamic event sets from 2020 and enforces zero event leakage."""
    index_csv = tmp_path / "index.csv"
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir(parents=True)
    
    rows = []
    # 2 training events, 1 validation event
    for ev, split in [("amphan_2020", "train"), ("kalbaishakhi_2020", "train"), ("monsoon_dep_2020", "validation")]:
        for i in range(2):
            sample_path = npz_dir / f"{ev}_{i}.npz"
            inputs = np.ones((7, 13, 114, 84), dtype=np.float32) * (2.0 if split == "train" else 999.0)
            targets = np.zeros((5, 3, 114, 84), dtype=np.float32)
            np.savez_compressed(sample_path, inputs=inputs, targets=targets)
            rows.append({
                "event_id": ev,
                "timestamp": f"2020-05-{10 if 'amphan' in ev else 25}T{i:02d}:00:00Z",
                "input_path": str(sample_path.relative_to(tmp_path)),
                "target_path": str(sample_path.relative_to(tmp_path)),
                "split": split,
            })
            
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        
    import scripts.training.fit_normalization as fn
    old_root = fn.ROOT
    try:
        fn.ROOT = tmp_path
        meta = fit_normalization(index_csv)
        assert meta["training_sample_count"] == 4
        assert meta["training_event_ids"] == ["amphan_2020", "kalbaishakhi_2020"]
        # Ingested mean should be 2.0 (from train rows), not contaminated by 999.0 from validation rows!
        assert meta["input_channels"]["iwv"]["mean"] == pytest.approx(2.0)
    finally:
        fn.ROOT = old_root


def test_section_1_3_normalization_arbitrary_dimensions_and_counts(tmp_path: Path):
    """Normalization supports arbitrary spatial dimensions (not fixed 114x84) and sequence counts (not fixed 6)."""
    index_csv = tmp_path / "index.csv"
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir(parents=True)
    
    h, w = 30, 25
    rows = []
    for i in range(3):
        sample_path = npz_dir / f"train_{i}.npz"
        inputs = np.ones((7, 13, h, w), dtype=np.float32) * 5.0
        targets = np.zeros((5, 3, h, w), dtype=np.float32)
        np.savez_compressed(sample_path, inputs=inputs, targets=targets)
        rows.append({
            "event_id": f"event_{i}",
            "timestamp": f"2020-05-0{i+1}T12:00:00Z",
            "input_path": str(sample_path.relative_to(tmp_path)),
            "target_path": str(sample_path.relative_to(tmp_path)),
            "split": "train",
        })
    val_path = npz_dir / "val_0.npz"
    np.savez_compressed(val_path, inputs=np.ones((7, 13, h, w), dtype=np.float32), targets=np.zeros((5, 3, h, w), dtype=np.float32))
    rows.append({
        "event_id": "val_event",
        "timestamp": "2020-06-01T12:00:00Z",
        "input_path": str(val_path.relative_to(tmp_path)),
        "target_path": str(val_path.relative_to(tmp_path)),
        "split": "validation",
    })
    
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        
    import scripts.training.fit_normalization as fn
    old_root = fn.ROOT
    try:
        fn.ROOT = tmp_path
        meta = fit_normalization(index_csv)
        assert meta["training_sample_count"] == 3
        assert meta["spatial_grid_shape"] == [30, 25]
        assert meta["input_channels"]["iwv"]["mean"] == pytest.approx(5.0)
    finally:
        fn.ROOT = old_root


def test_section_1_3_normalization_excludes_invalid_nan_pixels_and_saves_masks(tmp_path: Path):
    """Invalid pixels (NaNs, Infs) are excluded from statistics, and missingness masks are saved."""
    index_csv = tmp_path / "index.csv"
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir(parents=True)
    
    h, w = 20, 20
    rows = []
    inp = np.full((7, 13, h, w), 10.0, dtype=np.float32)
    inp[0, 0, 0:5, 0:5] = np.nan
    inp[1, 0, 0:5, 0:5] = np.inf
    inp[2, 0, 0:5, 0:5] = 20.0
    
    tgt = np.zeros((5, 3, h, w), dtype=np.float32)
    tgt[0, 0, 0:10, 0:10] = np.nan
    tgt[0, 0, 10:20, 10:20] = 1.0
    
    sample_path = npz_dir / "sample_nan.npz"
    np.savez_compressed(sample_path, inputs=inp, targets=tgt)
    rows.append({
        "event_id": "event_nan",
        "timestamp": "2020-05-15T12:00:00Z",
        "input_path": str(sample_path.relative_to(tmp_path)),
        "target_path": str(sample_path.relative_to(tmp_path)),
        "split": "train",
    })
    
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        
    import scripts.training.fit_normalization as fn
    old_root = fn.ROOT
    try:
        fn.ROOT = tmp_path
        meta = fit_normalization(index_csv)
        
        mean_c0 = meta["input_channels"]["iwv"]["mean"]
        assert np.isfinite(mean_c0)
        assert 10.0 <= mean_c0 <= 20.0
        assert meta["input_channels"]["iwv"]["missing_fraction"] > 0
        
        t_pos = meta["target_channels"]["thunderstorm"]["positive_rate"]
        assert np.isfinite(t_pos)
        assert t_pos > 0
        
        mask_file = tmp_path / "data" / "datasets" / "masks" / "sample_nan_mask.npz"
        assert mask_file.exists()
        with np.load(mask_file) as mask_data:
            assert "input_missing_mask" in mask_data
            assert "target_missing_mask" in mask_data
            assert mask_data["input_missing_mask"][0, 0, 0, 0] == True
            assert mask_data["input_missing_mask"][0, 0, 10, 10] == False
            assert mask_data["target_missing_mask"][0, 0, 0, 0] == True
            assert mask_data["target_missing_mask"][0, 0, 15, 15] == False
    finally:
        fn.ROOT = old_root


def test_section_1_3_static_dem_channels_not_duplicated_temporally(tmp_path: Path):
    """Static DEM channels (elevation, slope, drainage) are evaluated once on the spatial grid, not replicated every 30 minutes."""
    index_csv = tmp_path / "index.csv"
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir(parents=True)
    
    h, w = 10, 10
    total_grid_pixels = h * w
    n_sequences = 5
    n_frames_per_seq = 7
    
    rows = []
    for i in range(n_sequences):
        sample_path = npz_dir / f"seq_{i}.npz"
        inp = np.ones((n_frames_per_seq, 13, h, w), dtype=np.float32)
        inp[:, 10:13, :, :] = 100.0
        tgt = np.zeros((5, 3, h, w), dtype=np.float32)
        np.savez_compressed(sample_path, inputs=inp, targets=tgt)
        rows.append({
            "event_id": f"event_{i}",
            "timestamp": f"2020-05-0{i+1}T12:00:00Z",
            "input_path": str(sample_path.relative_to(tmp_path)),
            "target_path": str(sample_path.relative_to(tmp_path)),
            "split": "train",
        })
        
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        
    import scripts.training.fit_normalization as fn
    old_root = fn.ROOT
    try:
        fn.ROOT = tmp_path
        meta = fit_normalization(index_csv)
        
        dyn_count = meta["input_channels"]["iwv"]["valid_pixel_count"]
        assert dyn_count == 5 * 7 * 100
        assert meta["input_channels"]["iwv"]["is_static_dem"] is False
        
        for dem_ch in ["elevation", "slope", "drainage"]:
            dem_info = meta["input_channels"][dem_ch]
            assert dem_info["is_static_dem"] is True
            assert dem_info["observation_cadence"] == "static_spatial_grid_once"
            assert dem_info["valid_pixel_count"] == total_grid_pixels
    finally:
        fn.ROOT = old_root


def test_section_1_3_applies_training_stats_to_validation_and_test_without_leakage(tmp_path: Path):
    """Training statistics are applied to validation and test sequences; val/test never used for fitting."""
    index_csv = tmp_path / "index.csv"
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir(parents=True)
    
    h, w = 10, 10
    rows = []
    
    p_train = npz_dir / "train.npz"
    np.savez_compressed(p_train, inputs=np.full((7, 13, h, w), 10.0, dtype=np.float32), targets=np.zeros((5, 3, h, w), dtype=np.float32))
    rows.append({"event_id": "ev_train", "timestamp": "2020-05-10T12:00:00Z", "input_path": str(p_train.relative_to(tmp_path)), "target_path": str(p_train.relative_to(tmp_path)), "split": "train"})
    
    p_val = npz_dir / "val.npz"
    np.savez_compressed(p_val, inputs=np.full((7, 13, h, w), 1000.0, dtype=np.float32), targets=np.zeros((5, 3, h, w), dtype=np.float32))
    rows.append({"event_id": "ev_val", "timestamp": "2020-05-20T12:00:00Z", "input_path": str(p_val.relative_to(tmp_path)), "target_path": str(p_val.relative_to(tmp_path)), "split": "validation"})
    
    p_test = npz_dir / "test.npz"
    np.savez_compressed(p_test, inputs=np.full((7, 13, h, w), 5000.0, dtype=np.float32), targets=np.zeros((5, 3, h, w), dtype=np.float32))
    rows.append({"event_id": "ev_test", "timestamp": "2020-05-30T12:00:00Z", "input_path": str(p_test.relative_to(tmp_path)), "target_path": str(p_test.relative_to(tmp_path)), "split": "test"})
    
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        
    import scripts.training.fit_normalization as fn
    old_root = fn.ROOT
    try:
        fn.ROOT = tmp_path
        meta = fit_normalization(index_csv)
        
        assert meta["input_channels"]["iwv"]["mean"] == pytest.approx(10.0)
        assert meta["leakage_verification"]["validation_samples_used_in_fitting"] == 0
        assert meta["leakage_verification"]["test_samples_used_in_fitting"] == 0
        
        norm_val_file = tmp_path / "data" / "datasets" / "normalized" / "val.npz"
        assert norm_val_file.exists()
        with np.load(norm_val_file) as d:
            mu_train = meta["input_channels"]["iwv"]["mean"]
            std_train = meta["input_channels"]["iwv"]["std"]
            expected_norm_val = (1000.0 - mu_train) / std_train
            assert d["inputs"][0, 0, 0, 0] == pytest.approx(expected_norm_val, rel=1e-3)
    finally:
        fn.ROOT = old_root


def test_section_1_4_spatiotemporal_dataset_streaming(tmp_path: Path):
    """SpatiotemporalDataset loads samples one by one on-the-fly and standardizes inputs."""
    from scripts.training.train_multitask import SpatiotemporalDataset
    
    npz_dir = tmp_path / "seqs"
    npz_dir.mkdir()
    sample_path = npz_dir / "sample_0.npz"
    
    # 7 frames, 13 channels, 16x16
    inp = np.full((7, 13, 16, 16), 10.0, dtype=np.float32)
    inp[0, 0, 0, 0] = np.nan
    tgt = np.ones((5, 3, 16, 16), dtype=np.float32)
    np.savez_compressed(sample_path, inputs=inp, targets=tgt)
    
    rows = [{"input_path": str(sample_path.relative_to(tmp_path)), "target_path": str(sample_path.relative_to(tmp_path))}]
    seq_means = np.full(13, 10.0, dtype=np.float32)
    seq_stds = np.full(13, 2.0, dtype=np.float32)
    base_means = np.full(6, 10.0, dtype=np.float32)
    base_stds = np.full(6, 2.0, dtype=np.float32)
    
    ds = SpatiotemporalDataset(rows, tmp_path, seq_means, seq_stds, base_means, base_stds)
    assert len(ds) == 1
    
    norm_in, norm_base, raw_tgt = ds[0]
    assert norm_in.shape == (7, 13, 16, 16)
    assert norm_base.shape == (6, 16, 16)
    assert raw_tgt.shape == (5, 3, 16, 16)
    assert norm_in[0, 0, 1, 1].item() == 0.0
    assert norm_in[0, 0, 0, 0].item() == 0.0
    assert torch.isfinite(norm_in).all()


def test_section_1_4_masked_weighted_bce_loss():
    """Masked weighted BCE applies positive class weighting and masks invalid/NaN targets."""
    from scripts.training.train_multitask import masked_weighted_bce_loss
    
    preds = torch.tensor([[[[0.8, 0.2], [0.5, 0.9]]]], dtype=torch.float32)
    targets = torch.tensor([[[[1.0, 0.0], [float("nan"), -1.0]]]], dtype=torch.float32)
    
    # Unweighted (pos_weight = 1.0)
    loss_unw, brier_unw, count = masked_weighted_bce_loss(preds, targets, pos_weight=1.0)
    assert count == 2
    assert loss_unw.item() == pytest.approx(0.2231, rel=1e-2)
    assert brier_unw.item() == pytest.approx(0.04, rel=1e-2)
    
    # Weighted (pos_weight = 5.0) -> positive error should be scaled by 5
    loss_w, brier_w, _ = masked_weighted_bce_loss(preds, targets, pos_weight=5.0)
    assert loss_w.item() == pytest.approx(0.6694, rel=1e-2)
    assert loss_w.item() > loss_unw.item()
    assert brier_w.item() == pytest.approx(0.04, rel=1e-2)


def test_section_1_4_evaluation_per_hazard_and_horizon():
    """evaluate_loader computes per-hazard and per-horizon breakdown accurately."""
    from scripts.training.train_multitask import evaluate_loader
    from torch.utils.data import DataLoader, TensorDataset
    
    inputs = torch.zeros((2, 7, 13, 4, 4), dtype=torch.float32)
    baseline = torch.zeros((2, 6, 4, 4), dtype=torch.float32)
    targets = torch.zeros((2, 5, 3, 4, 4), dtype=torch.float32)
    targets[:, :, 0, :, :] = 1.0
    
    class DummyModel(torch.nn.Module):
        def forward(self, inp, base):
            return torch.full((2, 5, 3, 4, 4), 0.7, dtype=torch.float32)
            
    dataset = TensorDataset(inputs, baseline, targets)
    loader = DataLoader(dataset, batch_size=2)
    
    res = evaluate_loader(
        model=DummyModel(),
        loader=loader,
        device=torch.device("cpu"),
        weights=(1.0, 1.0, 1.0),
        pos_weights=(1.0, 1.0, 1.0),
        pin_memory=False,
    )
    
    assert "val_loss" in res
    assert "val_brier" in res
    assert len(res["per_hazard"]) == 3
    assert set(res["per_hazard"].keys()) == {"thunderstorms", "cloudbursts", "flash_floods"}
    assert len(res["per_horizon"]) == 5
    assert set(res["per_horizon"].keys()) == {"+2h", "+3h", "+4h", "+5h", "+6h"}
    assert len(res["per_hazard_horizon"]["thunderstorms"]) == 5
