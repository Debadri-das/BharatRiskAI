from typing import List
from datetime import datetime
import numpy as np
import xarray as xr

def extract_qpe_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    """Extract QPE features for the given bounding box and time range."""
    data = {
        'qpe': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10)),
        'rainfall': (['time', 'lat', 'lon'], np.random.rand(2, 10, 10))
    }
    return xr.Dataset(data)