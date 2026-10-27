"""Great-circle distance (haversine). Straight-line only, not road distance."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two WGS84 points."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))


def format_distance(metres: float) -> str:
    if metres < 1000:
        return f"{round(metres / 10) * 10:.0f} m"
    return f"{metres / 1000:.1f} km"
