import h5py
import glob
import numpy as np

# --------------------------------------------------
# Configuration
# --------------------------------------------------

TARGET_LAT = 22.57
TARGET_LON = 88.36

files = glob.glob("*.h5")

if not files:
    raise FileNotFoundError("No .h5 file found in this folder.")

filename = files[0]

print("Opening:", filename)

# --------------------------------------------------
# Open HDF5
# --------------------------------------------------

with h5py.File(filename, "r") as f:

    # ==========================
    # 4 km products
    # ==========================

    lat = f["Latitude"][:] * 0.01
    lon = f["Longitude"][:] * 0.01

    tir1_dn = f["IMG_TIR1"][0]
    tir2_dn = f["IMG_TIR2"][0]

    tir1_temp_lut = f["IMG_TIR1_TEMP"][:]
    tir2_temp_lut = f["IMG_TIR2_TEMP"][:]

    tir1_rad_lut = f["IMG_TIR1_RADIANCE"][:]
    tir2_rad_lut = f["IMG_TIR2_RADIANCE"][:]

    # Find closest pixel to Kolkata
    distance = (lat - TARGET_LAT)**2 + (lon - TARGET_LON)**2

    # Ignore invalid geolocation
    distance[(lat == 327.67) | (lon == 327.67)] = np.inf

    row, col = np.unravel_index(np.argmin(distance), distance.shape)

    actual_lat = lat[row, col]
    actual_lon = lon[row, col]

    print("\n==============================")
    print("KOLKATA 4 KM PIXEL")
    print("==============================")

    print("Requested:")
    print("Latitude :", TARGET_LAT)
    print("Longitude:", TARGET_LON)

    print("\nNearest satellite pixel:")
    print("Latitude :", actual_lat)
    print("Longitude:", actual_lon)

    # TIR1
    dn1 = int(tir1_dn[row, col])

    if dn1 != 1023 and dn1 < len(tir1_temp_lut):
        print("\nTIR-1")
        print("DN        :", dn1)
        print("Radiance  :", tir1_rad_lut[dn1])
        print("BT (K)    :", tir1_temp_lut[dn1])
        print("BT (°C)   :", tir1_temp_lut[dn1] - 273.15)
    else:
        print("\nTIR-1: INVALID / FILL VALUE")

    # TIR2
    dn2 = int(tir2_dn[row, col])

    if dn2 != 1023 and dn2 < len(tir2_temp_lut):
        print("\nTIR-2")
        print("DN        :", dn2)
        print("Radiance  :", tir2_rad_lut[dn2])
        print("BT (K)    :", tir2_temp_lut[dn2])
        print("BT (°C)   :", tir2_temp_lut[dn2] - 273.15)
    else:
        print("\nTIR-2: INVALID / FILL VALUE")

    # ==========================
    # 8 km WV product
    # ==========================

    lat_wv = f["Latitude_WV"][:] * 0.01
    lon_wv = f["Longitude_WV"][:] * 0.01

    wv_dn = f["IMG_WV"][0]

    wv_temp_lut = f["IMG_WV_TEMP"][:]
    wv_rad_lut = f["IMG_WV_RADIANCE"][:]

    distance_wv = (lat_wv - TARGET_LAT)**2 + (lon_wv - TARGET_LON)**2

    distance_wv[
        (lat_wv == 327.67) | (lon_wv == 327.67)
    ] = np.inf

    wv_row, wv_col = np.unravel_index(
        np.argmin(distance_wv),
        distance_wv.shape
    )

    actual_wv_lat = lat_wv[wv_row, wv_col]
    actual_wv_lon = lon_wv[wv_row, wv_col]

    wv_dn_value = int(wv_dn[wv_row, wv_col])

    print("\n==============================")
    print("KOLKATA WV PIXEL")
    print("==============================")

    print("Latitude :", actual_wv_lat)
    print("Longitude:", actual_wv_lon)

    if wv_dn_value != 1023 and wv_dn_value < len(wv_temp_lut):

        print("\nWater Vapour")
        print("DN        :", wv_dn_value)
        print("Radiance  :", wv_rad_lut[wv_dn_value])
        print("BT (K)    :", wv_temp_lut[wv_dn_value])
        print("BT (°C)   :", wv_temp_lut[wv_dn_value] - 273.15)

    else:
        print("\nWater Vapour: INVALID / FILL VALUE")

print("\n==============================")
print("Extraction complete.")
print("==============================")