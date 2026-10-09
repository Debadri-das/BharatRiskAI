import os
import glob
import json
import pandas as pd
import numpy as np
import rasterio

# Base directories
ground_truth_dir = os.path.join("data", "ground_truth")
labels_dir = os.path.join("data", "datasets", "labels")
jsonl_path = os.path.join(labels_dir, "labels.jsonl")

# Ensure output directory exists and clear old manifest
os.makedirs(labels_dir, exist_ok=True)
open(jsonl_path, 'w').close()

def write_jsonl_record(hazard, iso_ts, label, source, rel_path):
    record = {
        "hazard": hazard,
        "timestamp": iso_ts,
        "label": int(label),
        "source_type": source,
        "label_grid_path": rel_path
    }
    with open(jsonl_path, 'a') as f:
        f.write(json.dumps(record) + "\n")

print("Initialized labels.jsonl...")

# ==========================================
# 1. Process ALL Cloudburst CSVs
# ==========================================
print("Processing all Cloudburst labels...")
for csv_file in glob.glob(os.path.join(ground_truth_dir, "cloudburst", "*.csv")):
    df = pd.read_csv(csv_file)
    for _, row in df.iterrows():
        ts = pd.to_datetime(row['timestamp_utc'])
        iso_ts = ts.strftime("%Y-%m-%dT00:00:00+00:00")
        file_ts = ts.strftime("%Y%m%dT000000")
        
        grid_array = np.array([[int(row['is_cloudburst'])]], dtype=np.int8)
        npz_rel_path = f"data/ground_truth/cloudburst/{file_ts}.npz"
        npz_full_path = os.path.join(ground_truth_dir, "cloudburst", f"{file_ts}.npz")
        
        np.savez_compressed(npz_full_path, grid=grid_array)
        write_jsonl_record("cloudburst", iso_ts, row['is_cloudburst'], "imd_report", npz_rel_path)

# ==========================================
# 2. Process ALL Thunderstorm CSVs
# ==========================================
print("Processing all Thunderstorm labels...")
for csv_file in glob.glob(os.path.join(ground_truth_dir, "thunderstorm", "*.csv")):
    df = pd.read_csv(csv_file)
    for ts_str, group in df.groupby('timestamp_utc'):
        ts = pd.to_datetime(ts_str)
        iso_ts = ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        file_ts = ts.strftime("%Y%m%dT%H%M%S")
        
        is_active = group['is_thunderstorm'].any()
        grid_array = np.array([[int(is_active)]], dtype=np.int8)
        npz_rel_path = f"data/ground_truth/thunderstorm/{file_ts}.npz"
        npz_full_path = os.path.join(ground_truth_dir, "thunderstorm", f"{file_ts}.npz")
        
        np.savez_compressed(npz_full_path, grid=grid_array)
        write_jsonl_record("thunderstorm", iso_ts, is_active, "imd_report", npz_rel_path)

# ==========================================
# 3. Process ALL Flash Flood TIFs
# ==========================================
print("Processing all Flash Flood masks...")
# We map the exact sensing time for each satellite pass
flood_timestamps = {
    "amphan_flood_mask.tif": "2020-05-22T23:55:25+00:00",
    "yaas_flood_mask.tif": "2021-05-26T12:12:36+00:00",
    "remal_flood_mask.tif": "2024-06-03T12:12:51+00:00"
}

for tif_file in glob.glob(os.path.join(ground_truth_dir, "flash_flood", "*.tif")):
    basename = os.path.basename(tif_file)
    if basename in flood_timestamps:
        iso_ts = flood_timestamps[basename]
        # Convert ISO to the required filename timestamp format (e.g., 20210526T121236)
        file_ts = iso_ts.replace('-', '').replace(':', '')[:15]
        
        with rasterio.open(tif_file) as src:
            grid = src.read(1)
            # If any flood pixels exist (label=1) else 0
            overall_label = 1 if np.any(grid == 1) else 0
            
            npz_rel_path = f"data/ground_truth/flash_flood/{file_ts}.npz"
            npz_full_path = os.path.join(ground_truth_dir, "flash_flood", f"{file_ts}.npz")
            
            np.savez_compressed(npz_full_path, grid=grid)
            write_jsonl_record("flash_flood", iso_ts, overall_label, "sentinel1_flood_extent", npz_rel_path)

print(f"\nSuccess! Formatting complete. Your manifest file now contains ALL 3 events.")