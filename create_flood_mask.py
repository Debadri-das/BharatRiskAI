import os
import glob
import numpy as np
import rasterio

# 1. Define folder paths based on your structure
raw_data_dir = "data/sentinel-1"
output_dir = "data/ground_truth/flash_flood"
output_file = os.path.join(output_dir, "amphan_flood_mask.tif")

print("Searching for extracted Sentinel-1 TIFF files...")
# 2. Automatically find the extracted .tiff file in the sentinel-1 folder
search_pattern = os.path.join(raw_data_dir, "**", "*.tiff")
tiff_files = glob.glob(search_pattern, recursive=True)

if not tiff_files:
    print("Error: No .tiff files found. Did you extract the .zip file in the sentinel-1 folder?")
    exit()

# Use the first measurement file found (usually the VV polarization)
input_tiff = tiff_files[0]
print(f"Found radar image: {os.path.basename(input_tiff)}")
print("Processing flood mask... (This might take a minute for a large satellite image)")

# 3. Open the satellite image and process it
with rasterio.open(input_tiff) as src:
    # Read the radar backscatter values
    radar_data = src.read(1)
    
    # 4. Create the binary mask
    # Water reflects very little radar back to the satellite, so it has a low numerical value.
    # We apply a basic threshold to isolate the darkest pixels (water).
    # Note: 0 is often the "nodata" edge of the image, so we look for values slightly above 0 but very low.
    flood_mask = np.where((radar_data > 0) & (radar_data < 50), 1, 0).astype('uint8')
    
    # Copy the spatial metadata (coordinates, projection) from the original file
    profile = src.profile
    profile.update(
        dtype=rasterio.uint8,
        count=1,
        compress='lzw' # Compress the output file so it isn't massive
    )
    
    # 5. Save the final mask to your ground_truth folder
    with rasterio.open(output_file, 'w', **profile) as dst:
        dst.write(flood_mask, 1)

print(f"\nSuccess! Flash flood mask saved to: {output_file}")