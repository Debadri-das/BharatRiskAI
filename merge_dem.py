from pathlib import Path
import rasterio
from rasterio.crs import CRS
from rasterio.merge import merge

# 1. Configure paths using your project root
PROJECT_ROOT = Path(r"C:\Users\dasde\BharatRiskAI")
RAW_DEM_DIR = PROJECT_ROOT / "data" / "dem" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "dem"
OUTPUT_FILE = OUTPUT_DIR / "kolkata_dem.tif"

# 2. Locate all extracted tile files (.hgt or .tif) recursively
input_files = list(RAW_DEM_DIR.glob("**/*.hgt")) + list(RAW_DEM_DIR.glob("**/*.tif"))

if not input_files:
    raise FileNotFoundError(
        f"No .hgt or .tif files found in {RAW_DEM_DIR}!\n"
        "Ensure you have extracted your NASA Earthdata zip files there."
    )

print(f"Found {len(input_files)} tile(s) to merge:")
for f in input_files:
    print(f"  - {f.name}")

# 3. Open source rasters
src_files = [rasterio.open(f) for f in input_files]

try:
    # 4. Merge tiles into a single 2D raster array
    mosaic, out_transform = merge(src_files)

    # 5. Build output metadata
    out_meta = src_files[0].meta.copy()

    # Guarantee CRS is valid (NASADEM uses WGS84 / EPSG:4326)
    assigned_crs = src_files[0].crs if src_files[0].crs else CRS.from_epsg(4326)

    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "count": mosaic.shape[0],
        "transform": out_transform,
        "crs": assigned_crs,
        "compress": "lzw"  # Reduces output file size without data loss
    })

    # 6. Ensure destination directory exists and write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUTPUT_FILE, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"\nMerged DEM saved to: {OUTPUT_FILE}")

finally:
    # 7. Release file handles
    for src in src_files:
        src.close()