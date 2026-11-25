import numpy as np

from ml.atmosphere.features import (
    bulk_wind_shear_0_6km,
    horizontal_convergence,
    integrated_water_vapour,
    specific_humidity_from_relative_humidity,
)
import pytest


def test_specific_humidity_and_iwv_preserve_physical_units():
    pressure = np.array([1000.0, 900.0, 800.0])
    temperature = np.full((3, 1, 1), 300.0)
    rh = np.full((3, 1, 1), 50.0)
    q = specific_humidity_from_relative_humidity(temperature, rh, pressure[:, None, None])
    assert np.isfinite(q).all()
    assert 0 < integrated_water_vapour(q, pressure).item() < 100


def test_zero_wind_has_zero_convergence():
    lat = np.array([22.0, 23.0, 24.0])
    lon = np.array([86.0, 87.0, 88.0])
    result = horizontal_convergence(np.zeros((3, 3)), np.zeros((3, 3)), lat, lon)
    assert np.allclose(result, 0)


def test_wind_shear_interpolates_to_six_km():
    height = np.array([0.0, 3000.0, 6000.0])[:, None, None]
    u = np.array([0.0, 10.0, 20.0])[:, None, None]
    v = np.zeros_like(u)
    shear, shear_u, shear_v = bulk_wind_shear_0_6km(u, v, height)
    assert np.isclose(shear.item(), 20.0)
    assert np.isclose(shear_u.item(), 20.0)
    assert np.isclose(shear_v.item(), 0.0)


def test_cape_requires_a_complete_profile():
    from ml.atmosphere.features import surface_based_cape_cin

    temperature = np.full((3, 1, 1), 300.0)
    humidity = np.full((3, 1, 1), 50.0)
    with pytest.raises((ValueError, RuntimeError)):
        surface_based_cape_cin(temperature, humidity, np.array([100000.0, 90000.0]))
