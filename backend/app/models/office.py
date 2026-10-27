"""Verified real-world complaint channels: offices, portals, helplines and apps.

Every row must cite the official page it was taken from (`source_url`) and the
date it was checked (`verified_on`). Details that the source does not state are
left NULL rather than guessed. Rows are loaded from
`app/location/data/hyderabad_offices.json` by `python -m app.scripts.load_offices`.

Categories are stored as a JSON list of category slugs (`category_slugs`)
rather than a many-to-many table: the data is curated reference data keyed by
the stable slugs used in the seed file, it must load even before/without
matching category rows, and the dataset is small. The special slug "*" marks
channels relevant to every category (e.g. the national emergency number).
"""

import enum
from datetime import date

from sqlalchemy import Boolean, Date, Enum, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ALL_CATEGORIES = "*"


class ChannelType(str, enum.Enum):
    OFFICE = "office"
    ONLINE_PORTAL = "online_portal"
    HELPLINE = "helpline"
    MOBILE_APP = "mobile_app"


class SourceType(str, enum.Enum):
    OFFICIAL = "official"
    THIRD_PARTY = "third_party"


def _enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(enum_cls, name=name, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class Office(TimestampMixin, Base):
    __tablename__ = "offices"
    __table_args__ = (UniqueConstraint("name", "organisation", name="uq_offices_name_organisation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organisation: Mapped[str] = mapped_column(String(200), nullable=False)
    channel_type: Mapped[ChannelType] = mapped_column(_enum(ChannelType, "channeltype"), index=True, nullable=False)
    # JSONB so "serves category X" is an indexed-capable containment query (@>).
    category_slugs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    address: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(String(120))
    pincode: Mapped[str | None] = mapped_column(String(6))
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="Hyderabad")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    coordinates_source: Mapped[str | None] = mapped_column(String(255))

    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))

    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType, "sourcetype"), nullable=False)
    verified_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None
