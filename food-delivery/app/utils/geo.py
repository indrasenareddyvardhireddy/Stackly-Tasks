import math

EARTH_RADIUS_KM = 6371.0088
AVG_SPEED_KMPH = 20.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km between two lat/lon points (Haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def travel_minutes(distance_km: float, speed_kmph: float = AVG_SPEED_KMPH) -> float:
    return distance_km / speed_kmph * 60.0
