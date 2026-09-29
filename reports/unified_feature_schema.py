# Unified Feature Schema for BharatRiskAI

## Overview
This document defines the exact 13 model channels required by the `SpatiotemporalMTLNet` architecture and their mapping to real INSAT, IMDAA, and DEM data sources.

## Channel Definitions & Data Sources

### 1. Integrated Water Vapor (IWV)
- **Unified ID**: `iwv`
- **Source**: IMDAA pressure-level data
- **Unit**: kg/m²
- **Processing**: Integrated from specific humidity and pressure levels using `integrated_water_vapor` in `ingestion/real_data.py`.
- **Note**: `wv_radiance` from INSAT-3DR is NOT used as a direct proxy for IWV.

### 2. IWV Change
- **Unified ID**: `iwv_change`
- **Source**: IMDAA pressure-level data
- **Unit**: kg/m² per 30 minutes
- **Processing**: Temporal derivative of `iwv`.

### 3. Cloud Top Temperature (CTT)
- **Unified ID**: `ctt`
- **Source**: INSAT-3DR TIR1 (10.8 µm) brightness temperature
- **Unit**: °C
- **Processing**: `tir1_bt_c` from `scripts/features/satellite_features.py`.
- **Contract Note**: This is a **PROXY** for CTT. The TIR1 window channel approximates cloud-top temperature for optically thick clouds and is typically slightly warmer than true CTT.

### 4. CTT Drop Rate
- **Unified ID**: `ctt_drop_rate`
- **Source**: INSAT-3DR TIR1 brightness temperature
- **Unit**: °C per 30 minutes
- **Processing**: `ctt_cooling_rate` from `scripts/features/satellite_features.py` (calculated as `-ctt_change / elapsed_hours`).

### 5. Quantitative Precipitation Estimation (QPE)
- **Unified ID**: `qpe`
- **Source**: INSAT-3DR HEM (Hydro-Estimator Method) product
- **Unit**: mm/hr
- **Processing**: `qpe_rate_mm_hr` from `scripts/features/qpe_features.py`.

### 6. Rainfall
- **Unified ID**: `rainfall`
- **Source**: IMDAA pressure-level data
- **Unit**: mm/hr
- **Processing**: Reanalysis-based surface rainfall rate.

### 7. Convective Available Potential Energy (CAPE)
- **Unified ID**: `cape`
- **Source**: IMDAA pressure-level data
- **Unit**: J/kg
- **Processing**: Calculated from thermodynamic profile using `metpy`.

### 8. Convective Inhibition (CIN)
- **Unified ID**: `cin`
- **Source**: IMDAA pressure-level data
- **Unit**: J/kg
- **Processing**: Calculated from thermodynamic profile using `metpy`.

### 9. Convergence
- **Unified ID**: `convergence`
- **Source**: IMDAA pressure-level data
- **Unit**: 1/s
- **Processing**: Low-level horizontal wind convergence calculated from u-wind and v-wind components.

### 10. Wind Shear
- **Unified ID**: `wind_shear`
- **Source**: IMDAA pressure-level data
- **Unit**: m/s
- **Processing**: Vertical wind shear (surface to 6km) calculated from u-wind and v-wind components.

### 11. Elevation
- **Unified ID**: `elevation`
- **Source**: SRTM/CartoDEM data
- **Unit**: meters
- **Processing**: Static elevation grid from `scripts/features/dem_features.py`.

### 12. Slope
- **Unified ID**: `slope`
- **Source**: DEM data
- **Unit**: degrees
- **Processing**: Terrain slope calculated from elevation gradient in `scripts/features/dem_features.py`.

### 13. Drainage
- **Unified ID**: `drainage`
- **Source**: DEM data
- **Unit**: score (0-100)
- **Processing**: Terrain drainage/accumulation score from `scripts/features/dem_features.py`.

---

## Canonical Channel Ordering

```python
CHANNEL_ORDER = [
    "iwv",
    "iwv_change",
    "ctt",
    "ctt_drop_rate",
    "qpe",
    "rainfall",
    "cape",
    "cin",
    "convergence",
    "wind_shear",
    "elevation",
    "slope",
    "drainage",
]
```

## Baseline Channel Ordering

```python
BASELINE_ORDER = [
    "qpe",
    "cin",
    "rainfall",
    "convergence",
    "wind_shear",
    "elevation",
]
```


