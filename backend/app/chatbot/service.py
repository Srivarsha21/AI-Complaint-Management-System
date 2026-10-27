"""Stateless complaint-guidance conversation.

Flow per request: understand the issue (intent + category from the user's
messages) -> ask for a location when none was given -> return guidance built
only from verified records in the database (offices nearest first, plus
portals and helplines). If no record exists, say so instead of guessing.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chatbot import grounding, templates
from app.chatbot.categories import CategoryDetection, detect_category
from app.chatbot.intents import Intent, detect_intent
from app.location import geocoding
from app.location.office_search import Point, search
from app.models.office import ALL_CATEGORIES, ChannelType
from app.models.user import User
from app.repositories import office_repository
from app.schemas.chatbot import (
    CategoryRef,
    ChatRequest,
    ChatResponse,
    FileComplaintLink,
    LocationInput,
    ResolvedLocation,
)
from app.schemas.office import OfficeOut

logger = logging.getLogger(__name__)


@dataclass
class _Location:
    resolved: ResolvedLocation | None
    status: str
    note: str | None = None


def _detect_from_conversation(request: ChatRequest) -> tuple[CategoryDetection, str]:
    """Category from the latest user message, falling back to earlier ones (newest first)."""
    user_texts = [m.content for m in request.messages if m.role == "user"]
    latest = user_texts[-1]
    detection = detect_category(latest)
    if detection.slug or detection.alternatives:
        return detection, latest
    for text in reversed(user_texts[:-1]):
        earlier = detect_category(text)
        if earlier.slug:
            return earlier, text
    return detection, latest


def _resolve_location(location: LocationInput | None, conversation_text: str) -> _Location:
    if location is not None and location.latitude is not None and location.longitude is not None:
        inside = geocoding.in_hyderabad_region(location.latitude, location.longitude)
        resolved = ResolvedLocation(
            latitude=location.latitude, longitude=location.longitude, source="device", in_coverage_area=inside
        )
        return _Location(resolved, "resolved", None if inside else templates.OUTSIDE_AREA)

    # Typed locality / PIN, or a PIN code mentioned in the messages themselves.
    text = location.text if location is not None else geocoding.extract_pincode(conversation_text)
    if not text:
        return _Location(None, "not_provided")
    try:
        result = geocoding.get_geocoder().geocode(text)
    except geocoding.GeocodingUnavailable:
        return _Location(None, "unavailable", templates.LOCATION_UNAVAILABLE)
    if result is None:
        return _Location(None, "not_found", templates.LOCATION_NOT_FOUND.format(text=text[:60]))
    resolved = ResolvedLocation(
        latitude=result.latitude,
        longitude=result.longitude,
        label=result.label or text,
        source="geocoded",
        coordinates_source=result.source,
        in_coverage_area=True,
    )
    return _Location(resolved, "resolved")


def _category_ref(db: Session, slug: str) -> CategoryRef:
    category = office_repository.active_category_by_slug(db, slug)
    if category is None:
        return CategoryRef(id=None, slug=slug, name=templates.category_name(slug))
    return CategoryRef(id=category.id, slug=category.slug, name=category.name)


def _emergency_channels(db: Session) -> list[OfficeOut]:
    _, channels = search(db, None)
    return [c for c in channels if ALL_CATEGORIES in c.category_slugs]


def _guidance_reply(
    category: CategoryRef, offices: list[OfficeOut], channels: list[OfficeOut], location: _Location,
    *, emergency: bool, needs_location: bool,
) -> str:
    lines: list[str] = []
    if emergency:
        emergency_lines = [templates.describe_channel(c) for c in channels if ALL_CATEGORIES in c.category_slugs]
        lines.append("If anyone is in danger right now, get emergency help first:")
        lines += [f"- {line}" for line in emergency_lines] or [f"- {templates.EMERGENCY_NO_DATA}"]
        lines.append("")

    category_channels = [c for c in channels if ALL_CATEGORIES not in c.category_slugs]
    intro = templates.problem_intro(category.name)
    if not offices and not category_channels:
        lines.append(f"{intro} {templates.NO_DATA}")
        return "\n".join(lines)

    lines.append(intro)
    helplines = [c for c in category_channels if c.channel_type == ChannelType.HELPLINE]
    online = [c for c in category_channels if c.channel_type != ChannelType.HELPLINE]
    if helplines:
        lines.append("Official helplines:")
        lines += [f"- {templates.describe_channel(c)}" for c in helplines]
    if online:
        lines.append(templates.online_summary(len(online), with_helplines=bool(helplines)))
    if location.note:
        lines += ["", location.note]
    if needs_location:
        lines += ["", templates.ASK_LOCATION]
    elif offices:
        with_distance = [o for o in offices if o.distance_m is not None]
        if with_distance:
            lines += ["", "Nearest listed office:", f"- {templates.describe_office(with_distance[0])}"]
            lines.append("Distances are straight-line estimates, not road distances.")
        else:
            lines += ["", "Listed offices:"] + [f"- {templates.describe_office(o)}" for o in offices[:3]]
    return "\n".join(lines)


def _identity_terms(user: User | None) -> list[str]:
    """The account's name parts and email, redacted before anything is sent to Gemini."""
    if user is None:
        return []
    names = [user.full_name, *user.full_name.split()] if user.full_name else []
    return [*names, user.email]


def handle(db: Session, request: ChatRequest, user: User | None = None) -> ChatResponse:
    latest = request.messages[-1].content
    intent = detect_intent(latest)

    if intent in (Intent.GREETING, Intent.THANKS):
        reply = templates.GREETING if intent == Intent.GREETING else templates.THANKS
        return ChatResponse(
            reply=reply, intent=intent.value, category=None, needs_location=False,
            suggestions=templates.QUICK_SUGGESTIONS, disclaimer=templates.disclaimer([]),
        )

    detection, source_text = _detect_from_conversation(request)
    emergency = intent == Intent.EMERGENCY

    if detection.slug is None:
        channels = _emergency_channels(db) if emergency else []
        if detection.alternatives:
            names = [templates.category_name(s) for s in detection.alternatives]
            reply = templates.AMBIGUOUS.format(options=" or ".join(names))
            suggestions = names
        else:
            reply = templates.UNKNOWN
            suggestions = templates.QUICK_SUGGESTIONS
        if emergency:
            first = [templates.describe_channel(c) for c in channels] or [templates.EMERGENCY_NO_DATA]
            reply = "If anyone is in danger right now, get emergency help first:\n" + "\n".join(
                f"- {line}" for line in first
            ) + "\n\n" + reply
        return ChatResponse(
            reply=reply, intent=intent.value, category=None, needs_location=False, channels=channels,
            suggestions=suggestions, disclaimer=templates.disclaimer([c.verified_on for c in channels]),
        )

    category = _category_ref(db, detection.slug)
    conversation_text = " ".join(m.content for m in request.messages if m.role == "user")
    location = _resolve_location(request.location, conversation_text)
    origin = Point(location.resolved.latitude, location.resolved.longitude) if location.resolved else None
    offices, channels = search(db, detection.slug, origin)
    # Only ask where the user is when that can actually change the answer.
    needs_location = location.status == "not_provided" and any(o.latitude is not None for o in offices)

    template_reply = _guidance_reply(
        category, offices, channels, location, emergency=emergency, needs_location=needs_location
    )
    records = offices + channels
    reply, generated_by = template_reply, "template"
    if records:
        rephrased = grounding.rephrase(template_reply, records, source_text, identity_terms=_identity_terms(user))
        if rephrased:
            reply, generated_by = rephrased, "gemini"

    return ChatResponse(
        reply=reply,
        intent=intent.value,
        category=category,
        needs_location=needs_location,
        location=location.resolved,
        location_status=location.status,
        offices=offices,
        channels=channels,
        steps=templates.steps_for(detection.slug, can_file_in_app=category.id is not None),
        documents=None,
        disclaimer=templates.disclaimer([r.verified_on for r in records]),
        file_complaint=FileComplaintLink(category_id=category.id) if category.id is not None else None,
        generated_by=generated_by,
    )
