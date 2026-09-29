# INSAT-3DR L1C Product Contract

## Accepted File Formats
- HDF5 (.h5)
- NetCDF (.nc, .nc4)

## Required Datasets
- Water Vapor (IMG_WV)
- Thermal Infrared (IMG_TIR1, IMG_TIR2)
- Visible (IMG_VIS)

## Required Calibration Metadata
- Radiance calibration coefficients (lab_radiance_quad, lab_radiance_scale_factor, lab_radiance_add_offset)
- Brightness temperature lookup tables (IMG_TIR1_TEMP, IMG_WV_TEMP)
- Fill/missing value indicators (_FillValue, fill_value, missing_value)

## Timestamp Requirements
- Acquisition time (Acquisition_Start_Time)
- ISO 8601 format (YYYY-MM-DDTHH:MM:SS)
- UTC timezone

## Latitude/Longitude Requirements
- 1D or 2D arrays
- EPSG:4326 (WGS84)
- Resolution: 0.01 degrees
- Range: 85.7°E to 89.9°E, 21.5°N to 27.2°N

## Supported Channels
- Water Vapor Radiance
- Thermal Infrared Brightness Temperature (TIR1, TIR2)
- Visible Radiance

## Study Region
- Kolkata Metropolitan Area
- Bounding Box: 85.7°E to 89.9°E, 21.5°N to 27.2°N

## Missing-Data Behavior
- Fill values are replaced with NaN
- Invalid counts (1023) are explicitly excluded
- Non-finite values are replaced with NaN

## Calibration Notes
- Water Vapor Radiance: Quadratic + Linear calibration
- TIR Brightness Temperature: Lookup table conversion
- WV radiance is NOT Integrated Water Vapor (IWV)
- Visible Albedo: Optional, if available

## Provenance
- Source: MOSDAC
- Processing: BharatRiskAI
- Version: 1.0

## Standardized Extracted Product
The standardized extracted product must contain:
```text
timestamp
latitude
longitude
wv_radiance
wv_radiance_change
wv_rate
wv_spatial_gradient
tir1_bt_k
tir2_bt_k
vis_radiance
vis_albedo_percent (optional)
```

## Example Metadata
```json
{
  "source": "INSAT-3DR",
  "timestamp": "2023-07-15T12:30:00+00:00",
  "region": {"west": 85.7, "south": 21.5, "east": 89.9, "north": 27.2},
  "source_crs": "EPSG:4326",
  "channels": ["wv_radiance", "tir1_bt_k", "tir2_bt_k", "vis_radiance"],
  "calibration": "Radiance uses lab_radiance_quad + scale_factor*count + add_offset; TIR uses provider temperature LUT; WV remains radiance, not IWV."
}
```