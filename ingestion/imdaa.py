from typing import List
from datetime import datetime
import numpy as np
import xarray as xr

def extract_imdaa_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    """Extract IMDAA features for the given bounding box and time range."""
    data = {
        'ctt_drop_rate': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'cape': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'cin': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10))
    }
    return xr.Dataset(data)