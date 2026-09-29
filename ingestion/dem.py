from typing import List
import numpy as np
import xarray as xr

def extract_dem_features(bbox: List[float]) -> xr.Dataset:
    """Extract DEM features for the given bounding box."""
    data = {
        'elevation': (['lat', 'lon'], np.random.rand(10, 10)),
        'slope': (['lat', 'lon'], np.random.rand(10, 10)),
        'drainage': (['lat', 'lon'], np.random.rand(10, 10))
    }
    return xr.Dataset(data)