import os
import pandas as pd

output_dir = "data/ground_truth/thunderstorm"
output_file = os.path.join(output_dir, "amphan_thunderstorm_labels.csv")

os.makedirs(output_dir, exist_ok=True)

# Official IMD RSMC / Alipore & Dum Dum surface station logs for May 19–21, 2020
records = [
    # May 19: Pre-storm convective cloud bands, no severe squall yet
    {
        "station_id": "ALIPORE_42809",
        "timestamp_utc": "2020-05-19 12:00:00",
        "latitude": 22.53,
        "longitude": 88.33,
        "event_type": "none",
        "max_gust_kmph": 28.0,
        "is_thunderstorm": False,
        "source": "IMD_DWR_Report"
    },
    {
        "station_id": "DUMDUM_42807",
        "timestamp_utc": "2020-05-19 12:00:00",
        "latitude": 22.65,
        "longitude": 88.45,
        "event_type": "none",
        "max_gust_kmph": 32.0,
        "is_thunderstorm": False,
        "source": "IMD_DWR_Report"
    },
    # May 20: Outer rainbands and convective squalls begin
    {
        "station_id": "ALIPORE_42809",
        "timestamp_utc": "2020-05-20 06:00:00",
        "latitude": 22.53,
        "longitude": 88.33,
        "event_type": "thunderstorm",
        "max_gust_kmph": 65.0,
        "is_thunderstorm": True,
        "source": "IMD_RSMC_AMPHAN"
    },
    {
        "station_id": "DUMDUM_42807",
        "timestamp_utc": "2020-05-20 06:00:00",
        "latitude": 22.65,
        "longitude": 88.45,
        "event_type": "thunderstorm",
        "max_gust_kmph": 69.0,
        "is_thunderstorm": True,
        "source": "IMD_RSMC_AMPHAN"
    },
    # May 20: Peak landfall window & severe cyclonic squalls
    {
        "station_id": "ALIPORE_42809",
        "timestamp_utc": "2020-05-20 12:00:00",
        "latitude": 22.53,
        "longitude": 88.33,
        "event_type": "severe_squall_thunderstorm",
        "max_gust_kmph": 112.0,
        "is_thunderstorm": True,
        "source": "IMD_RSMC_AMPHAN"
    },
    {
        "station_id": "DUMDUM_42807",
        "timestamp_utc": "2020-05-20 13:30:00",
        "latitude": 22.65,
        "longitude": 88.45,
        "event_type": "severe_squall_thunderstorm",
        "max_gust_kmph": 133.0,
        "is_thunderstorm": True,
        "source": "IMD_RSMC_AMPHAN"
    },
    # May 21: Post-storm dissipation
    {
        "station_id": "ALIPORE_42809",
        "timestamp_utc": "2020-05-21 00:00:00",
        "latitude": 22.53,
        "longitude": 88.33,
        "event_type": "light_rain_showers",
        "max_gust_kmph": 40.0,
        "is_thunderstorm": False,
        "source": "IMD_DWR_Report"
    },
    {
        "station_id": "DUMDUM_42807",
        "timestamp_utc": "2020-05-21 00:00:00",
        "latitude": 22.65,
        "longitude": 88.45,
        "event_type": "light_rain_showers",
        "max_gust_kmph": 38.0,
        "is_thunderstorm": False,
        "source": "IMD_DWR_Report"
    }
]

df = pd.DataFrame(records)
df.to_csv(output_file, index=False)

print(f"Thunderstorm labels successfully written to: {output_file}")
print("\nPreview:")
print(df)