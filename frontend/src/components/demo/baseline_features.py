"""
Baseline feature schema for the SpatiotemporalMTLNet model.

The model expects 6 baseline channels representing thermodynamic and wind features.
These are derived from IMDAA and DEM data.
"""

BASELINE_FEATURES = [
    "cape",
    "cin",
    "convergence",
    "wind_shear",
    "elevation",
    "slope"
]

"""
Physical meaning and source of each baseline feature:

1. cape: Convective Available Potential Energy (J/kg) - IMDAA thermodynamic data
2. cin: Convective Inhibition (J/kg) - IMDAA thermodynamic data
3. convergence: Low-level convergence (unitless) - IMDAA wind data
4. wind_shear: Wind shear (m/s) - IMDAA wind data
5. elevation: Terrain elevation (meters) - DEM data
6. slope: Terrain slope (degrees) - DEM data
"""