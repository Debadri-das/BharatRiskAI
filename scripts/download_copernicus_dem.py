"""Download and mosaic Copernicus DEM GLO-30 tiles for West Bengal, then derive terrain/drainage features."""
import concurrent.futures
from pathlib import Path
import sys
import time
import urllib.request
import rasterio
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "dem" / "raw" / "copernicus_glo30"
OUTPUT_TIF = ROOT / "data" / "dem" / "BharatRiskAI_WestBengal_DEM_GLO30.tif"

BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
LATS = range(21, 28)  # 21 to 27
LONS = range(85, 90)  # 85 to 89


def download_tile(lat: int, lon: int) -> Path:
    tile_name = f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"
    url = f"{BASE_URL}/{tile_name}/{tile_name}.tif"
    dest = RAW_DIR / f"{tile_name}.tif"
    
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
        
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_suffix(".tmp")
    
    # Download with retry
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BharatRiskAI-Pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_dest, "wb") as out:
                out.write(resp.read())
            tmp_dest.replace(dest)
            print(f"Downloaded: {tile_name} ({dest.stat().st_size / (1024**2):.1f} MB)")
            return dest
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Failed to download {tile_name} after 3 attempts: {e}")
            time.sleep(2)


def main():
    print(f"=== 1. DOWNLOADING COPERNICUS GLO-30 TILES ({len(LATS)*len(LONS)} TILES) ===")
    t0 = time.time()
    tiles = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download_tile, lat, lon): (lat, lon) for lat in LATS for lon in LONS}
        for future in concurrent.futures.as_completed(futures):
            tiles.append(future.result())
            
    print(f"All {len(tiles)} tiles secured in {time.time()-t0:.1f}s.")
    
    print("\n=== 2. MOSAICING REGIONAL TILES INTO MASTER GeoTIFF ===")
    t1 = time.time()
    src_files = [rasterio.open(t) for t in sorted(tiles)]
    try:
        mosaic, out_transform = merge(src_files)
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "crs": "EPSG:4326",
            "compress": "lzw",
            "nodata": -9999.0
        })
        
        OUTPUT_TIF.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(OUTPUT_TIF, "w", **out_meta) as dst:
            dst.write(mosaic)
        print(f"Saved master DEM to {OUTPUT_TIF} ({OUTPUT_TIF.stat().st_size / (1024**2):.1f} MB) in {time.time()-t1:.1f}s.")
    finally:
        for s in src_files:
            s.close()
            
    print("\n=== 3. DERIVING HYDROLOGICAL DRAINAGE & TOPOGRAPHY ===")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.features.dem_features import build
    output_npz = ROOT / "data" / "derived" / "terrain" / "dem_features.npz"
    build(OUTPUT_TIF, output_npz)
    print(f"Hydrological terrain features saved to {output_npz}")
    print("ALL DONE SUCCESSFULLY!")


if __name__ == "__main__":
    main()
