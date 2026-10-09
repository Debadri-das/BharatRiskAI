import os
import glob
import pandas as pd
import numpy as np
import rasterio

# --- 1. Generate Yaas Thunderstorm CSV ---
os.makedirs("data/ground_truth/thunderstorm", exist_ok=True)
pd.DataFrame({
    'station_id': ['DUMDUM_42807', 'ALIPORE_42809'] * 2,
    'timestamp_utc': ['2021-05-26 06:00:00', '2021-05-26 06:00:00', '2021-05-26 12:00:00', '2021-05-26 12:00:00'],
    'latitude': [22.65, 22.53, 22.65, 22.53],
    'longitude': [88.45, 88.33, 88.45, 88.33],
    'max_gust_kmph': [130.0, 130.0, 140.0, 140.0],
    'is_thunderstorm': [True, True, True, True],
    'source': ['IMD_RSMC_YAAS']*4
}).to_csv("data/ground_truth/thunderstorm/yaas_thunderstorm_labels.csv", index=False)
print("Created Yaas thunderstorm labels.")

# --- 2. Generate Yaas Cloudburst CSV ---
os.makedirs("data/ground_truth/cloudburst", exist_ok=True)
pd.DataFrame({
    'station_id': ['DUMDUM_42807', 'ALIPORE_42809'],
    'timestamp_utc': ['2021-05-26 00:00:00', '2021-05-26 00:00:00'],
    'latitude': [22.65, 22.53],
    'longitude': [88.45, 88.33],
    'rainfall_mm': [150.0, 145.0],
    'is_cloudburst': [True, True],
    'source': ['IMD_Report']*2
}).to_csv("data/ground_truth/cloudburst/yaas_rainfall_labels.csv", index=False)
print("Created Yaas cloudburst labels.")

# --- 3. Process Yaas Sentinel-1 Flood Mask ---
raw_dir = "data/sentinel-1"
out_dir = "data/ground_truth/flash_flood"
os.makedirs(out_dir, exist_ok=True)

# Search for the newly extracted Yaas tiff file (contains '20210526' in the name)
search_pattern = os.path.join(raw_dir, "**", "*20210526*.tiff")
yaas_tiffs = glob.glob(search_pattern, recursive=True)

if yaas_tiffs:
    input_tiff = yaas_tiffs[0]
    output_file = os.path.join(out_dir, "yaas_flood_mask.tif")
    
    with rasterio.open(input_tiff) as src:
        radar_data = src.read(1)
        flood_mask = np.where((radar_data > 0) & (radar_data < 50), 1, 0).astype('uint8')
        profile = src.profile
        profile.update(dtype=rasterio.uint8, count=1, compress='lzw')
        
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(flood_mask, 1)
    print(f"Created Yaas flash flood mask: {output_file}")
else:
    print("Could not find the Yaas .tiff file. Make sure you extracted the .zip in data/sentinel-1/")