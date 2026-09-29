
from typing import Dict, List
from datetime import datetime
import numpy as np
import xarray as xr
from ingestion.insat import extract_insat_features
from ingestion.imdaa import extract_imdaa_features
from ingestion.dem import extract_dem_features
from ingestion.qpe import extract_qpe_features
from ingestion.satellite import get_satellite_provider
from reports.unified_feature_schema import FEATURE_SCHEMA

class UnifiedFeaturePipeline:
    def __init__(self, bbox, start_time, end_time):
        self.bbox = bbox
        self.start_time = start_time
        self.end_time = end_time
        self.feature_schema = FEATURE_SCHEMA

    def _combine_features(self, insat_features, imdaa_features, dem_features, qpe_features):
        unified_dataset = xr.Dataset()

        # Debug: Print channels from each dataset
        print("Channels in INSAT features:", list(insat_features.data_vars.keys()))
        print("Channels in IMDAA features:", list(imdaa_features.data_vars.keys()))
        print("Channels in DEM features:", list(dem_features.data_vars.keys()))
        print("Channels in QPE features:", list(qpe_features.data_vars.keys()))

        # Add features from INSAT
        for channel in self.feature_schema['insat']:
            if channel in insat_features:
                unified_dataset[channel] = insat_features[channel]

        # Add features from IMDAA
        for channel in self.feature_schema['imdaa']:
            if channel in imdaa_features:
                unified_dataset[channel] = imdaa_features[channel]

        # Add features from DEM
        for channel in self.feature_schema['dem']:
            if channel in dem_features:
                unified_dataset[channel] = dem_features[channel]

        # Add features from QPE
        for channel in self.feature_schema['qpe']:
            if channel in qpe_features:
                unified_dataset[channel] = qpe_features[channel]

        print("Channels in combined dataset:", list(unified_dataset.data_vars.keys()))
        return unified_dataset
