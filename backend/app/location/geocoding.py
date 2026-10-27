"""Geocoding of user-typed localities / PIN codes via OpenStreetMap Nominatim.

Follows the Nominatim usage policy: an identifying User-Agent (with a contact
address when configured), at most one request per second (process-wide), and
results are cached in memory so repeated questions do not hit the service.
Searches are bounded to a box around Hyderabad. Failures never break the
chatbot: callers catch `GeocodingUnavailable` and continue without distance.

Only the place text the user typed is sent; never their identity.
"""

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

COORDINATES_SOURCE = "OpenStreetMap Nominatim (approximate)"

# Box around Hyderabad, Secunderabad and the surrounding urban region
# (west, south, east, north) in decimal degrees.
HYDERABAD_BBOX = (78.15, 17.15, 78.80, 17.70)

_PIN_RE = re.compile(r"(?<!\d)([1-9]\d{5})(?!\d)")
_UNSAFE_CHARS = re.compile(r"[^\w\s,./#&()'-]", re.UNICODE)
_CITY_WORDS = ("hyderabad", "secunderabad", "telangana", "cyberabad")
MAX_QUERY_LENGTH = 200


class GeocodingUnavailable(Exception):
    """The geocoding service is disabled, unreachable or returned an error."""


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    label: str
    source: str = COORDINATES_SOURCE


class Geocoder(Protocol):
    def geocode(self, text: str) -> GeocodeResult | None:
        """Return a result, None when nothing matches, or raise GeocodingUnavailable."""


def extract_pincode(text: str) -> str | None:
    """The first 6-digit Indian PIN code in `text`, if any."""
    match = _PIN_RE.search(text or "")
    return match.group(1) if match else None


def is_pincode(text: str) -> bool:
    return bool(re.fullmatch(r"\s*[1-9]\d{5}\s*", text or ""))


def normalise_query(text: str) -> str:
    """Collapse whitespace, drop unusual characters and cap the length."""
    cleaned = _UNSAFE_CHARS.sub(" ", text or "")
    return " ".join(cleaned.split())[:MAX_QUERY_LENGTH].strip(" ,.")


def in_hyderabad_region(latitude: float, longitude: float) -> bool:
    west, south, east, north = HYDERABAD_BBOX
    return south <= latitude <= north and west <= longitude <= east


class NominatimGeocoder:
    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        contact_email: str | None = None,
        timeout_seconds: float = 8,
        min_interval_seconds: float = 1.0,
        cache_size: int = 512,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        agent = f"{user_agent} ({contact_email})" if contact_email else user_agent
        self._contact_email = contact_email
        self._client = client or httpx.Client(timeout=timeout_seconds, headers={"User-Agent": agent})
        if client is not None:
            self._client.headers["User-Agent"] = agent
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request: float | None = None
        self._throttle_lock = threading.Lock()
        self._cache: OrderedDict[str, GeocodeResult | None] = OrderedDict()
        self._cache_size = cache_size
        self._cache_lock = threading.Lock()

    # -- cache ---------------------------------------------------------------
    def _cached(self, key: str) -> tuple[bool, GeocodeResult | None]:
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return True, self._cache[key]
        return False, None

    def _remember(self, key: str, value: GeocodeResult | None) -> None:
        with self._cache_lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    # -- throttle ------------------------------------------------------------
    def _wait_for_slot(self) -> None:
        """Block so that requests are at least `min_interval` seconds apart."""
        if self._last_request is not None:
            wait = self._min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    # -- public API ----------------------------------------------------------
    def geocode(self, text: str) -> GeocodeResult | None:
        query = normalise_query(text)
        if len(query) < 3:
            return None
        key = query.lower()
        hit, value = self._cached(key)
        if hit:
            return value

        west, south, east, north = HYDERABAD_BBOX
        params: dict[str, str | int] = {
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "in",
            "viewbox": f"{west},{north},{east},{south}",
            "bounded": 1,
        }
        if is_pincode(query):
            params["postalcode"] = query.strip()
        else:
            lowered = query.lower()
            params["q"] = query if any(w in lowered for w in _CITY_WORDS) else f"{query}, Hyderabad"
        if self._contact_email:
            params["email"] = self._contact_email

        with self._throttle_lock:
            self._wait_for_slot()
            try:
                response = self._client.get(f"{self._base_url}/search", params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("geocoding failed: %s", exc.__class__.__name__)
                raise GeocodingUnavailable(str(exc)) from exc

        result = self._parse(payload)
        self._remember(key, result)
        return result

    @staticmethod
    def _parse(payload: object) -> GeocodeResult | None:
        if not isinstance(payload, list) or not payload:
            return None
        first = payload[0]
        try:
            lat, lng = float(first["lat"]), float(first["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        if not in_hyderabad_region(lat, lng):
            return None
        label = str(first.get("display_name") or "")[:200]
        return GeocodeResult(latitude=lat, longitude=lng, label=label)


class DisabledGeocoder:
    def geocode(self, text: str) -> GeocodeResult | None:
        raise GeocodingUnavailable("geocoding is disabled")


_geocoder: Geocoder | None = None
_geocoder_lock = threading.Lock()


def get_geocoder() -> Geocoder:
    """Process-wide geocoder (shared so the 1 request/second limit holds)."""
    global _geocoder
    with _geocoder_lock:
        if _geocoder is None:
            settings = get_settings()
            if settings.geocoding_enabled:
                _geocoder = NominatimGeocoder(
                    base_url=settings.nominatim_base_url,
                    user_agent=settings.nominatim_user_agent,
                    contact_email=settings.nominatim_contact_email,
                    timeout_seconds=settings.geocoding_timeout_seconds,
                )
            else:
                _geocoder = DisabledGeocoder()
        return _geocoder


def set_geocoder(geocoder: Geocoder | None) -> None:
    """Replace the shared geocoder (tests, or a different provider)."""
    global _geocoder
    with _geocoder_lock:
        _geocoder = geocoder
