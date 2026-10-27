"""Fixed wording for the guidance chatbot (the non-AI path, always available).

Steps are deliberately generic, accurate advice for any civic complaint; no
office-specific procedure is described unless it comes from a sourced record.
"""

from datetime import date

from app.location.distance import format_distance
from app.models.office import ChannelType
from app.schemas.office import OfficeOut

# Display names used when the category table has no row for a slug
# (mirrors the seeded categories).
CATEGORY_NAMES: dict[str, str] = {
    "drainage-sewerage": "Drainage & Sewerage",
    "garbage-sanitation": "Garbage & Sanitation",
    "roads-potholes": "Roads & Potholes",
    "street-lights": "Street Lights",
    "water-supply": "Water Supply",
    "electricity": "Electricity",
    "stray-animals": "Stray Animals",
    "encroachment": "Encroachment & Illegal Construction",
    "public-health": "Mosquito & Public Health",
    "pollution": "Noise & Air Pollution",
    "parks-trees": "Parks & Trees",
    "other": "Other",
}

QUICK_SUGGESTIONS = [
    "Drainage problem in my area",
    "Garbage not collected for days",
    "Street light not working",
    "No water supply since morning",
    "Power cut in my street",
    "Big pothole on the main road",
]

BASE_STEPS = [
    "Note the exact location: street or colony, a nearby landmark and the PIN code.",
    "If it is safe, take clear photos that show the problem and its surroundings.",
    "Register the complaint through one of the official channels listed here and write down the "
    "complaint or reference number you receive.",
    "If the problem is not fixed, follow up through the same channel and quote that reference number.",
]

SAFETY_TIPS: dict[str, str] = {
    "electricity": "Stay away from fallen, hanging or sparking wires and do not touch electric poles or transformers.",
    "drainage-sewerage": "Keep away from open manholes and overflowing drains, and warn others nearby if it is safe.",
    "stray-animals": "Do not approach aggressive animals; get medical attention promptly after any animal bite.",
    "parks-trees": "Keep away from fallen trees or branches, especially if they are touching electric wires.",
    "water-supply": "If the water looks or smells unusual, avoid drinking it without boiling or treating it.",
    "public-health": "Empty or cover containers holding stagnant water around your home where you can.",
}

IN_APP_STEP = "You can also file it in this app with the button below, so it is routed and tracked here."

GREETING = (
    "Hello! I can help you find the right official place to report a civic problem in Hyderabad. "
    "Tell me what the problem is, for example \"garbage not collected in my lane\"."
)
THANKS = "You're welcome. If you have another problem to report, just describe it."
UNKNOWN = (
    "I couldn't tell what kind of problem this is. Could you describe it in a few words, for example "
    "\"street light not working\" or \"drain overflowing\"? You can also pick one of the suggestions."
)
AMBIGUOUS = "Your message could fit more than one type of problem. Which one is closest: {options}?"
ASK_LOCATION = (
    "To show the nearest offices, share your location or type your locality or PIN code. "
    "The helplines and online options for this problem work from anywhere."
)
LOCATION_NOT_FOUND = (
    "I couldn't find \"{text}\" in Hyderabad, so distances are not shown. Try a nearby landmark, "
    "a bigger locality name or your 6-digit PIN code."
)
LOCATION_UNAVAILABLE = (
    "The location lookup service is not available right now, so distances are not shown. "
    "You can still use the channels below, or share your device location instead."
)
OUTSIDE_AREA = (
    "Your location appears to be outside the Hyderabad area. This assistant only has verified "
    "information for Hyderabad, so the offices below may not cover your area."
)
NO_DATA = (
    "I don't have verified official contact details for this type of problem yet, so I can't point you "
    "to a specific office. Please check the official website of your municipal corporation, or file the "
    "complaint in this app so it can be routed."
)
EMERGENCY_NO_DATA = "If anyone is in danger, contact emergency services immediately."


def category_name(slug: str) -> str:
    return CATEGORY_NAMES.get(slug, slug.replace("-", " ").title())


def steps_for(slug: str, *, can_file_in_app: bool) -> list[str]:
    steps = list(BASE_STEPS)
    if slug in SAFETY_TIPS:
        steps.insert(0, SAFETY_TIPS[slug])
    if can_file_in_app:
        steps.append(IN_APP_STEP)
    return steps


def problem_intro(name: str) -> str:
    article = "an" if name[:1].lower() in "aeiou" else "a"
    return f"This looks like {article} {name} problem."


def online_summary(count: int, *, with_helplines: bool) -> str:
    noun = "online option" if count == 1 else "online options"
    prefix = "There " + ("is also" if count == 1 else "are also") if with_helplines else "There " + (
        "is" if count == 1 else "are")
    return f"{prefix} {count} official {noun} (portals or apps) listed below."


def describe_channel(channel: OfficeOut) -> str:
    """One line built only from the record's own fields."""
    if channel.channel_type == ChannelType.HELPLINE and channel.phone:
        return f"{channel.name}: call {channel.phone}"
    if channel.website:
        return f"{channel.name}: {channel.website}"
    if channel.phone:
        return f"{channel.name}: phone {channel.phone}"
    return f"{channel.name}: email {channel.email}"


def describe_office(office: OfficeOut) -> str:
    text = office.name
    if office.address:
        text += f", {office.address}"
    if office.distance_m is not None:
        text += f" - about {format_distance(office.distance_m)} away in a straight line"
    return text


def disclaimer(verified_dates: list[date]) -> str:
    text = ""
    if verified_dates:
        text = (
            "Contact details shown here come only from official government websites, last checked on "
            f"{max(verified_dates):%d %b %Y}. "
        )
    return text + (
        "Offices, numbers and procedures can change, and this assistant cannot guarantee that any office "
        "will accept your complaint, so please confirm with the department. "
        "In an emergency, contact emergency services immediately."
    )
