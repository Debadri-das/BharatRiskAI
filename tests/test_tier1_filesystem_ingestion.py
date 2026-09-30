"""Small local fixtures for Tier-1 discovery/validation only (not weather claims)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from ingestion.real_data import discover_tier1_files, validate_dem_file, validate_imdaa_file, validate_insat_npz, validate_tier1_sources


def _insat(path, *, qpe=False, timestamp="2026-01-01T00:00:00+00:00"):
    values = {"timestamp": timestamp, "latitude": np.array([22.0, 23.0]), "longitude": np.array([88.0, 89.0])}
    if qpe:
        values["qpe"] = np.ones((2, 2), dtype=np.float32)
    else:
        values.update(wv_radiance=np.ones((2, 2), dtype=np.float32), tir1_bt_k=np.full((2, 2), 280.0, dtype=np.float32))
    np.savez(path, **values)


def test_discovery_and_validation_are_deterministic(tmp_path):
    (tmp_path / "data" / "insat" / "l1c").mkdir(parents=True)
    (tmp_path / "data" / "insat" / "qpe").mkdir(parents=True)
    _insat(tmp_path / "data" / "insat" / "l1c" / "frame.npz")
    _insat(tmp_path / "data" / "insat" / "qpe" / "qpe_frame.npz", qpe=True)
    files = discover_tier1_files(tmp_path)
    assert files["wv"] == files["tir"]
    assert [path.name for path in files["qpe"]] == ["qpe_frame.npz"]
    assert validate_insat_npz(files["wv"][0], "wv")["product"] == "wv"
    report = validate_tier1_sources(tmp_path)
    assert report["errors"]["imdaa"] == "no files discovered"


def test_canonical_satellite_adapters_read_fixture_arrays(tmp_path, monkeypatch):
    from ingestion.insat import extract_insat_features
    from ingestion.qpe import extract_qpe_features

    l1c = tmp_path / "data" / "insat" / "l1c"
    qpe = tmp_path / "data" / "insat" / "qpe"
    l1c.mkdir(parents=True)
    qpe.mkdir(parents=True)
    _insat(l1c / "frame.npz")
    _insat(qpe / "qpe_frame.npz", qpe=True)
    monkeypatch.setenv("BHARATRISK_DATA_ROOT", str(tmp_path))
    start = datetime(2025, 12, 31, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    satellite = extract_insat_features([87.0, 21.0, 90.0, 24.0], start, end)
    precipitation = extract_qpe_features([87.0, 21.0, 90.0, 24.0], start, end)
    assert set(satellite.data_vars) == {"ctt", "ctt_drop_rate"}
    assert set(precipitation.data_vars) == {"qpe"}


def test_insat_validation_rejects_bad_timestamp_and_geolocation(tmp_path):
    path = tmp_path / "bad.npz"
    np.savez(path, timestamp="not-a-time", latitude=np.array([95.0]), longitude=np.array([88.0]), wv_radiance=np.ones((1, 1)))
    with pytest.raises(ValueError, match="ISO-8601"):
        validate_insat_npz(path, "wv")


def test_imdaa_and_dem_validate_required_metadata(tmp_path):
    xr = pytest.importorskip("xarray")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    nc = tmp_path / "profile.nc"
    coords = {"time": [np.datetime64("2026-01-01T00:00")], "plev": ("plev", [1000.0, 850.0], {"units": "hPa"}), "lat": [22.0, 23.0], "lon": [88.0, 89.0]}
    data = {}
    for name, units in (("ta", "K"), ("hus", "kg kg-1"), ("ua", "m s-1"), ("va", "m s-1")):
        data[name] = (("time", "plev", "lat", "lon"), np.ones((1, 2, 2, 2), dtype=np.float32), {"units": units})
    ds = xr.Dataset(data, coords=coords)
    ds.to_netcdf(nc)
    assert validate_imdaa_file(nc)["timestamp"].startswith("2026-01-01T00:00:00")

    dem = tmp_path / "dem.tif"
    with rasterio.open(dem, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32", crs="EPSG:4326", transform=from_origin(88, 23, 0.05, 0.05)) as dst:
        dst.write(np.ones((1, 2, 2), dtype=np.float32))
        dst.update_tags(1, units="metres")
    assert validate_dem_file(dem)["units"] == "metres"
