import h5py
import numpy as np
import glob

TARGET_LAT = 22.57
TARGET_LON = 88.36

h5_file = glob.glob("*.h5")[0]

print("Opening:", h5_file)

with h5py.File(h5_file, "r") as f:

    hem = f["HEM"][0]

    # Latitude/longitude are stored as int16 with scale factor 0.01
    lat_raw = f["Latitude"][:]
    lon_raw = f["Longitude"][:]

    # IMPORTANT:
    # 32767 is the fill value, so mask it BEFORE applying scale factor.
    valid_geo = (
        (lat_raw != 32767) &
        (lon_raw != 32767)
    )

    lat = lat_raw.astype(np.float32) * 0.01
    lon = lon_raw.astype(np.float32) * 0.01

    # Only use valid geographic pixels
    distance = np.full(lat.shape, np.inf, dtype=np.float32)

    distance[valid_geo] = (
        (lat[valid_geo] - TARGET_LAT) ** 2 +
        (lon[valid_geo] - TARGET_LON) ** 2
    )

    row, col = np.unravel_index(
        np.argmin(distance),
        distance.shape
    )

    rainfall = hem[row, col]

    print()
    print("==============================")
    print("KOLKATA HEM / QPE")
    print("==============================")

    print("Requested:")
    print(f"Latitude : {TARGET_LAT}")
    print(f"Longitude: {TARGET_LON}")

    print()
    print("Nearest valid satellite pixel:")
    print(f"Latitude : {lat[row, col]:.2f}")
    print(f"Longitude: {lon[row, col]:.2f}")

    print()
    print("Hydro Estimator Precipitation:")

    if rainfall == -999:
        print("QPE       : No valid data")
    else:
        print(f"QPE       : {rainfall:.4f} mm/hr")

    print()
    print("==============================")
    print("Extraction complete.")
    print("==============================")