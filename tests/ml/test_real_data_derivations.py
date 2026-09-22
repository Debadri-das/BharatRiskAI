import numpy as np

from ingestion.real_data import cloud_top_temperature, integrated_water_vapor, temporal_change


def test_integrated_water_vapor_uses_pressure_column():
    pressure = np.array([100000.0, 80000.0, 60000.0])
    humidity = np.array([0.02, 0.01, 0.004])
    integrate = getattr(np, "trapezoid", np.trapz)
    expected = integrate(humidity[::-1], pressure[::-1]) / 9.80665
    assert np.isclose(integrated_water_vapor(humidity, pressure), expected)


def test_cloud_top_temperature_converts_kelvin():
    result = cloud_top_temperature(np.array([[225.0]]))
    assert np.isclose(result.item(), -48.15)


def test_temporal_change_returns_rate():
    current = np.array([[58.0]])
    previous = np.array([[50.0]])
    assert np.isclose(temporal_change(current, previous, 2).item(), 4.0)
