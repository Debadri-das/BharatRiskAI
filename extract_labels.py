import os
import xarray as xr
import pandas as pd

# 1. Define your file paths based on your folder structure
input_file = "data/imd/RF25_ind2020_rfp25.nc"
output_folder = "data/ground_truth/cloudburst"
output_file = f"{output_folder}/amphan_rainfall_labels.csv"

# Make sure the ground_truth/cloudburst folder exists, create it if it doesn't
os.makedirs(output_folder, exist_ok=True)

print("Opening IMD rainfall data...")
# 2. Open the downloaded NetCDF file
ds = xr.open_dataset(input_file)

# 3. Define Kolkata's exact coordinates
kolkata_lat = 22.57
kolkata_lon = 88.36

print("Extracting data for Kolkata (May 19-21, 2020)...")
# 4. Extract data specifically for Kolkata and the dates of Cyclone Amphan
# The script matches the exact axes names (LONGITUDE, LATITUDE, TIME) inside the file
kolkata_data = ds.sel(
    LONGITUDE=kolkata_lon, 
    LATITUDE=kolkata_lat, 
    method="nearest"
).sel(TIME=slice("2020-05-19", "2020-05-21"))

# 5. Convert this specific data into a standard table
df = kolkata_data.to_dataframe().reset_index()

# 6. Format the table to match your machine learning pipeline's rules
formatted_df = pd.DataFrame({
    "station_id": "IMD_GRID_KOLKATA",
    "timestamp_utc": df["TIME"],
    "latitude": df["LATITUDE"],
    "longitude": df["LONGITUDE"],
    "daily_rainfall_mm": df["RAINFALL"] # Pulls from the RAINFALL variable in the file
})

# 7. Add the specific 'is_cloudburst' True/False label
# We mark it True if rainfall for the day crossed the 100mm extreme threshold
formatted_df["is_cloudburst"] = formatted_df["daily_rainfall_mm"] >= 100
formatted_df["source"] = "IMD_Gridded_0.25"

# 8. Save the table as a CSV file for your ML model to read
formatted_df.to_csv(output_file, index=False)

print(f"Success! Your ground truth labels are saved at: {output_file}")
print("\nHere is a preview of the data:")
print(formatted_df)