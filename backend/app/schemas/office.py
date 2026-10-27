"""Office / complaint-channel schemas: seed-file records and API responses."""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.office import ALL_CATEGORIES, ChannelType, SourceType

_PIN_RE = re.compile(r"^[1-9]\d{5}$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OfficeRecord(BaseModel):
    """One entry of `app/location/data/*.json`, validated before loading."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=200)
    organisation: str = Field(min_length=2, max_length=200)
    channel_type: ChannelType
    category_slugs: list[str] = Field(min_length=1)
    address: str | None = None
    locality: str | None = Field(default=None, max_length=120)
    pincode: str | None = None
    city: str = Field(default="Hyderabad", max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinates_source: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    website: HttpUrl | None = None
    # Required: no record is accepted without the official page it came from.
    source_url: HttpUrl
    source_type: SourceType
    verified_on: date
    notes: str | None = None
    is_active: bool = True

    @field_validator("category_slugs")
    @classmethod
    def _valid_slugs(cls, value: list[str]) -> list[str]:
        for slug in value:
            if slug != ALL_CATEGORIES and not _SLUG_RE.match(slug):
                raise ValueError(f"invalid category slug {slug!r}")
        return sorted(set(value))

    @field_validator("pincode")
    @classmethod
    def _valid_pin(cls, value: str | None) -> str | None:
        if value is not None and not _PIN_RE.match(value):
            raise ValueError("pincode must be a 6-digit Indian PIN code")
        return value

    @field_validator("verified_on")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("verified_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _coordinates_are_documented(self) -> "OfficeRecord":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be set or both be empty")
        if self.latitude is not None and not self.coordinates_source:
            raise ValueError("coordinates_source is required when coordinates are given")
        if self.channel_type == ChannelType.OFFICE and not self.address:
            raise ValueError("an office record needs an address")
        if self.channel_type != ChannelType.OFFICE and not (self.phone or self.website or self.email):
            raise ValueError("a channel record needs a phone, website or email")
        return self


class OfficeOut(BaseModel):
    """An office or channel as returned to clients, with derived map links."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    organisation: str
    channel_type: ChannelType
    category_slugs: list[str]
    address: str | None
    locality: str | None
    pincode: str | None
    city: str
    latitude: float | None
    longitude: float | None
    coordinates_source: str | None
    phone: str | None
    email: str | None
    website: str | None
    source_url: str
    source_type: SourceType
    verified_on: date
    notes: str | None
    distance_m: int | None = None
    map_url: str | None = None
    directions_url: str | None = None
    osm_directions_url: str | None = None


class OfficeSearchResult(BaseModel):
    offices: list[OfficeOut]
    channels: list[OfficeOut]
