from typing import List, Dict, Any
from datetime import datetime
import numpy as np
import xarray as xr

def extract_insat_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    """Extract INSAT features for the given bounding box and time range."""
    data = {
        'ctt': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'qpe': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'iwv': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'iwv_change': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10))
    }
    return xr.Dataset(data)