import os
import glob
import pandas as pd
import numpy as np
import rasterio

# --- 1. Generate Remal Thunderstorm CSV ---
os.makedirs("data/ground_truth/thunderstorm", exist_ok=True)
pd.DataFrame({
    'station_id': ['DUMDUM_42807', 'ALIPORE_42809'] * 2,
    'timestamp_utc': ['2024-05-26 18:00:00', '2024-05-26 18:00:00', '2024-05-27 00:00:00', '2024-05-27 00:00:00'],
    'latitude': [22.65, 22.53, 22.65, 22.53],
    'longitude': [88.45, 88.33, 88.45, 88.33],
    'max_gust_kmph': [110.0, 91.0, 100.0, 90.0],
    'is_thunderstorm': [True, True, True, True],
    'source': ['IMD_RSMC_REMAL']*4
}).to_csv("data/ground_truth/thunderstorm/remal_thunderstorm_labels.csv", index=False)
print("Created Remal thunderstorm labels.")

# --- 2. Generate Remal Cloudburst CSV ---
os.makedirs("data/ground_truth/cloudburst", exist_ok=True)
pd.DataFrame({
    'station_id': ['DUMDUM_42807', 'ALIPORE_42809'],
    'timestamp_utc': ['2024-05-27 00:00:00', '2024-05-27 00:00:00'],
    'latitude': [22.65, 22.53],
    'longitude': [88.45, 88.33],
    'rainfall_mm': [180.0, 160.0],
    'is_cloudburst': [True, True],
    'source': ['IMD_Report']*2
}).to_csv("data/ground_truth/cloudburst/remal_rainfall_labels.csv", index=False)
print("Created Remal cloudburst labels.")

# --- 3. Process Remal Sentinel-1 Flood Mask ---
raw_dir = "data/sentinel-1"
out_dir = "data/ground_truth/flash_flood"
os.makedirs(out_dir, exist_ok=True)

# Search for the newly extracted Remal tiff file (updated to June 2024)
search_pattern = os.path.join(raw_dir, "**", "*202406*.tiff")
remal_tiffs = glob.glob(search_pattern, recursive=True)

if remal_tiffs:
    input_tiff = remal_tiffs[0]
    output_file = os.path.join(out_dir, "remal_flood_mask.tif")
    
    with rasterio.open(input_tiff) as src:
        radar_data = src.read(1)
        # Identify flood water based on radar backscatter thresholds
        flood_mask = np.where((radar_data > 0) & (radar_data < 50), 1, 0).astype('uint8')
        profile = src.profile
        profile.update(dtype=rasterio.uint8, count=1, compress='lzw')
        
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(flood_mask, 1)
    print(f"Created Remal flash flood mask: {output_file}")
else:
    print("Could not find the Remal .tiff file. Make sure you extracted the .zip in data/sentinel-1/")