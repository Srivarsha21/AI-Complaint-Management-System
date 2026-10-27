"""Find verified offices and complaint channels for a category, nearest first.

Distance is only computed when both the user's and the office's coordinates
are known; otherwise `distance_m` stays empty and nothing is estimated.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.location import maps
from app.location.distance import haversine_m
from app.models.office import ChannelType, Office
from app.repositories import office_repository
from app.schemas.office import OfficeOut

# Helplines first (fastest for citizens), then portals, then apps.
_CHANNEL_ORDER = {ChannelType.HELPLINE: 0, ChannelType.ONLINE_PORTAL: 1, ChannelType.MOBILE_APP: 2}


@dataclass(frozen=True)
class Point:
    latitude: float
    longitude: float


def to_out(office: Office, origin: Point | None = None) -> OfficeOut:
    out = OfficeOut.model_validate(office)
    if office.has_coordinates:
        lat, lng = office.latitude, office.longitude
        out.map_url = maps.osm_map_url(lat, lng)
        out.directions_url = maps.google_directions_url(lat, lng)
        out.osm_directions_url = maps.osm_directions_url(lat, lng)
        if origin is not None:
            out.distance_m = round(haversine_m(origin.latitude, origin.longitude, lat, lng))
    return out


def _office_sort_key(out: OfficeOut) -> tuple:
    # Offices with a known distance first (nearest first), then the rest by name.
    return (out.distance_m is None, out.distance_m or 0, out.organisation, out.name)


def search(
    db: Session, category_slug: str | None, origin: Point | None = None, *, office_limit: int = 5
) -> tuple[list[OfficeOut], list[OfficeOut]]:
    """Return (physical offices, other channels) serving `category_slug`."""
    records = office_repository.list_active(db, category_slug)
    offices = sorted(
        (to_out(r, origin) for r in records if r.channel_type == ChannelType.OFFICE), key=_office_sort_key
    )
    channels = sorted(
        (to_out(r) for r in records if r.channel_type != ChannelType.OFFICE),
        key=lambda o: (_CHANNEL_ORDER.get(o.channel_type, 9), "*" in o.category_slugs, o.organisation, o.name),
    )
    return offices[:office_limit], channels
