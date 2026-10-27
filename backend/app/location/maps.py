"""Map and directions links built from a destination's coordinates only.

The user's own position is never put in a URL: the map apps ask for the
starting point (or use the device location) themselves.
"""

from urllib.parse import urlencode


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def osm_map_url(lat: float, lng: float, zoom: int = 17) -> str:
    """OpenStreetMap page with a marker at the destination."""
    la, lo = _fmt(lat), _fmt(lng)
    return f"https://www.openstreetmap.org/?{urlencode({'mlat': la, 'mlon': lo})}#map={zoom}/{la}/{lo}"


def osm_directions_url(lat: float, lng: float) -> str:
    """OpenStreetMap directions with only the destination filled in."""
    return "https://www.openstreetmap.org/directions?" + urlencode({"route": f";{_fmt(lat)},{_fmt(lng)}"})


def google_directions_url(lat: float, lng: float) -> str:
    """Google Maps directions deep link (destination only; app picks the origin)."""
    return "https://www.google.com/maps/dir/?" + urlencode({"api": "1", "destination": f"{_fmt(lat)},{_fmt(lng)}"})
