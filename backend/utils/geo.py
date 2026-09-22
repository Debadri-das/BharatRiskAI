from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def get_lat(item):
    return item["latitude"] if isinstance(item, dict) else item.latitude

def get_lon(item):
    return item["longitude"] if isinstance(item, dict) else item.longitude

def nearest(items, latitude: float, longitude: float):
    return min(items, key=lambda item: haversine_km(latitude, longitude, get_lat(item), get_lon(item)))
