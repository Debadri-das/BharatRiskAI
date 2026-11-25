"""Atmospheric derivations with explicit units and missing-data handling."""
from __future__ import annotations

import numpy as np

GRAVITY = 9.80665
EARTH_RADIUS_M = 6_371_000.0


def specific_humidity_from_relative_humidity(
    temperature_k: np.ndarray,
    relative_humidity_percent: np.ndarray,
    pressure_pa: np.ndarray,
) -> np.ndarray:
    """Derive specific humidity (kg/kg) using saturation vapour pressure."""
    temperature = np.asarray(temperature_k, dtype=float)
    rh = np.asarray(relative_humidity_percent, dtype=float)
    pressure = np.asarray(pressure_pa, dtype=float)
    if np.nanmedian(pressure) < 2_000:
        pressure = pressure * 100.0
    if np.nanmedian(temperature) < 150:
        raise ValueError("temperature_k must be in kelvin")
    valid_rh = rh[np.isfinite(rh)]
    if valid_rh.size > 0:
        median_rh = np.nanmedian(valid_rh)
        if median_rh < 0.0 or median_rh > 150.0:
            raise ValueError("relative humidity must be in percent in the range 0..100")
        if 0.0 <= median_rh <= 1.5 and np.nanmax(valid_rh) <= 2.0:
            rh = rh * 100.0
    rh = np.clip(rh, 0.0, 100.0)
    temperature, rh, pressure = np.broadcast_arrays(temperature, rh, pressure)
    valid = np.isfinite(temperature) & np.isfinite(rh) & np.isfinite(pressure) & (pressure > 0)
    result = np.full(temperature.shape, np.nan, dtype=float)
    tc = temperature - 273.15
    saturation_hpa = 6.112 * np.exp((17.67 * tc) / (tc + 243.5))
    vapour_hpa = (rh / 100.0) * saturation_hpa
    epsilon = 0.622
    result[valid] = epsilon * vapour_hpa[valid] / (pressure[valid] / 100.0 - (1 - epsilon) * vapour_hpa[valid])
    return result


def integrated_water_vapour(specific_humidity: np.ndarray, pressure_pa: np.ndarray) -> np.ndarray:
    """Integrate q dp/g over valid pressure levels, returning kg/m2."""
    q = np.asarray(specific_humidity, dtype=float)
    pressure = np.asarray(pressure_pa, dtype=float)
    if pressure.ndim != 1 or q.shape[0] != pressure.size:
        raise ValueError("specific humidity must be (level, ...) and pressure must be 1-D")
    if np.nanmedian(pressure) < 2_000:
        pressure = pressure * 100.0
    order = np.argsort(pressure)
    q = q[order]
    pressure = pressure[order]
    valid = np.isfinite(q) & np.isfinite(pressure[:, None, None])
    values = np.where(valid, q, np.nan)
    with np.errstate(invalid="ignore"):
        result = np.trapezoid(values, pressure, axis=0) / GRAVITY if hasattr(np, "trapezoid") else np.trapz(values, pressure, axis=0) / GRAVITY
    result[np.sum(valid, axis=0) < 2] = np.nan
    return result


def bulk_wind_shear_0_6km(
    u_wind: np.ndarray,
    v_wind: np.ndarray,
    geopotential_height_m: np.ndarray,
    *,
    surface_u: np.ndarray | None = None,
    surface_v: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate wind to 0 and 6000 m and return magnitude, du, and dv."""
    u = np.asarray(u_wind, dtype=float)
    v = np.asarray(v_wind, dtype=float)
    height = np.asarray(geopotential_height_m, dtype=float)
    if u.shape != v.shape or u.shape != height.shape or u.ndim != 3:
        raise ValueError("wind and geopotential height must share (level, lat, lon) shape")
    du = np.full(u.shape[1:], np.nan)
    dv = np.full(u.shape[1:], np.nan)
    for index in np.ndindex(u.shape[1:]):
        z = height[(slice(None),) + index]
        valid = np.isfinite(z) & np.isfinite(u[(slice(None),) + index]) & np.isfinite(v[(slice(None),) + index])
        if valid.sum() < 2 or np.nanmin(z[valid]) > 500.0 or np.nanmax(z[valid]) < 5500.0:
            continue
        order = np.argsort(z[valid])
        levels = z[valid][order]
        u_levels = u[(slice(None),) + index][valid][order]
        v_levels = v[(slice(None),) + index][valid][order]
        u0 = np.interp(0.0, levels, u_levels) if surface_u is None else surface_u[index]
        v0 = np.interp(0.0, levels, v_levels) if surface_v is None else surface_v[index]
        du[index] = np.interp(6000.0, levels, u_levels) - u0
        dv[index] = np.interp(6000.0, levels, v_levels) - v0
    return np.hypot(du, dv), du, dv


def surface_based_cape_cin(
    temperature_k: np.ndarray,
    relative_humidity_percent: np.ndarray,
    pressure_pa: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate surface-based CAPE/CIN with MetPy's documented convention."""
    try:
        from metpy.calc import cape_cin, dewpoint_from_relative_humidity, parcel_profile
        from metpy.units import units
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("metpy is required for CAPE/CIN derivation") from exc
    temperature = np.asarray(temperature_k, dtype=float)
    humidity = np.asarray(relative_humidity_percent, dtype=float)
    pressure = np.asarray(pressure_pa, dtype=float)
    if temperature.shape != humidity.shape or temperature.ndim != 3 or pressure.ndim != 1:
        raise ValueError("temperature and humidity must be (level, lat, lon), pressure must be 1-D")
    if temperature.shape[0] != pressure.size:
        raise ValueError("pressure and profile level dimensions do not match")
    order = np.argsort(pressure)[::-1]
    pressure = pressure[order]
    temperature = temperature[order]
    humidity = np.clip(humidity[order], 0.0, 100.0)
    cape = np.full(temperature.shape[1:], np.nan)
    cin = np.full(temperature.shape[1:], np.nan)
    for index in np.ndindex(cape.shape):
        t = temperature[(slice(None),) + index]
        rh = humidity[(slice(None),) + index]
        if not (np.isfinite(t).all() and np.isfinite(rh).all()):
            continue
        p = pressure * units.pascal
        t_quantity = t * units.kelvin
        dewpoint = dewpoint_from_relative_humidity(t_quantity, rh / 100.0)
        parcel = parcel_profile(p, t_quantity[0], dewpoint[0])
        cape_value, cin_value = cape_cin(p, t_quantity, dewpoint, parcel)
        cape[index] = cape_value.to("joule / kilogram").magnitude
        cin[index] = cin_value.to("joule / kilogram").magnitude
    return cape, cin


def horizontal_convergence(u_wind: np.ndarray, v_wind: np.ndarray, latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    """Calculate -div(V) on a latitude/longitude grid in s-1."""
    u = np.asarray(u_wind, dtype=float)
    v = np.asarray(v_wind, dtype=float)
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    if u.shape != v.shape or u.shape != (lat.size, lon.size):
        raise ValueError("wind shape must match latitude/longitude grid")
    phi = np.deg2rad(lat)
    lam = np.deg2rad(lon)
    cos_phi = np.cos(phi)[:, None]
    d_u_cos_d_lambda = np.gradient(u * cos_phi, lam, axis=1, edge_order=1)
    d_v_d_phi = np.gradient(v, phi, axis=0, edge_order=1)
    divergence = d_u_cos_d_lambda / (EARTH_RADIUS_M * cos_phi) + d_v_d_phi / EARTH_RADIUS_M
    return -divergence
