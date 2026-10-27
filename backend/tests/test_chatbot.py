"""Module 8: location-aware complaint guidance chatbot (no network: geocoder and Gemini are faked)."""

import re

import pytest

from app.chatbot import categories, grounding
from app.chatbot.categories import KeywordCategoryDetector, detect_category
from app.chatbot.intents import Intent, detect_intent
from app.location import geocoding
from app.location.geocoding import GeocodeResult, GeocodingUnavailable
from app.location.office_loader import load_file
from app.models import Office
from app.services import gemini_client
from tests.conftest import auth_header, login, make_category, make_user

CHAT = "/api/v1/chatbot/message"
SLUGS = {
    "drainage-sewerage": "Drainage & Sewerage", "garbage-sanitation": "Garbage & Sanitation",
    "roads-potholes": "Roads & Potholes", "street-lights": "Street Lights", "water-supply": "Water Supply",
    "electricity": "Electricity", "stray-animals": "Stray Animals", "encroachment": "Encroachment",
    "public-health": "Mosquito & Public Health", "pollution": "Noise & Air Pollution",
    "parks-trees": "Parks & Trees", "other": "Other",
}
KHAIRATABAD = {"latitude": 17.4126, "longitude": 78.4594}


class FakeGeocoder:
    def __init__(self, result=None, error: bool = False):
        self.result, self.error, self.queries = result, error, []

    def geocode(self, text):
        self.queries.append(text)
        if self.error:
            raise GeocodingUnavailable("down")
        return self.result


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Never reach Nominatim or Gemini from tests."""
    fake = FakeGeocoder()
    geocoding.set_geocoder(fake)
    monkeypatch.setattr(gemini_client, "is_configured", lambda: False)
    yield fake
    geocoding.set_geocoder(None)


@pytest.fixture
def tokens(client, db):
    make_user(db, email="chat@example.com", full_name="Lakshmi Reddy")
    return login(client, "chat@example.com")


@pytest.fixture
def seeded(db):
    cats = {slug: make_category(db, name=name, slug=slug, department=f"{name} Dept") for slug, name in SLUGS.items()}
    load_file(db)
    return cats


def chat(client, tokens, text, location=None, history=None):
    messages = (history or []) + [{"role": "user", "content": text}]
    payload = {"messages": messages}
    if location is not None:
        payload["location"] = location
    response = client.post(CHAT, json=payload, headers=auth_header(tokens))
    assert response.status_code == 200, response.text
    return response.json()


# --- Category and intent detection ------------------------------------------------

@pytest.mark.parametrize(
    "text, slug",
    [
        ("Drainage problem in my area", "drainage-sewerage"),
        ("manhole open near the school", "drainage-sewerage"),
        ("garbage not collected for 3 days", "garbage-sanitation"),
        ("chetta teeyatledu", "garbage-sanitation"),
        ("big pothole on the main road", "roads-potholes"),
        ("road pe bada gaddha hai", "roads-potholes"),
        ("street light not working in our lane", "street-lights"),
        ("no water supply since morning", "water-supply"),
        ("paani nahi aa raha", "water-supply"),
        ("current poyindi 5 hours nundi", "electricity"),
        ("power cut and low voltage", "electricity"),
        ("stray dogs chasing kids", "stray-animals"),
        ("kukkalu ekkuva unnayi", "stray-animals"),
        ("illegal construction on the footpath", "encroachment"),
        ("too many mosquitoes, need fogging", "public-health"),
        ("loudspeaker noise till midnight", "pollution"),
        ("tree fallen on the road", "parks-trees"),
        ("చెత్త తీయడం లేదు", "garbage-sanitation"),
        ("दोपहर से बिजली नहीं है", "electricity"),
    ],
)
def test_detect_category(text, slug):
    assert detect_category(text).slug == slug


def test_detect_category_unknown_and_ambiguous():
    assert detect_category("I want to know about my pension").slug is None
    tie = KeywordCategoryDetector().detect("dog near the tap")
    assert tie.slug is None and set(tie.alternatives) == {"stray-animals", "water-supply"}


def test_detector_can_be_swapped():
    class Fixed:
        def detect(self, text):
            return categories.CategoryDetection("pollution", 0.9)

    original = categories.get_detector()
    categories.set_detector(Fixed())
    try:
        assert detect_category("anything").slug == "pollution"
    finally:
        categories.set_detector(original)


@pytest.mark.parametrize(
    "text, intent",
    [("hi", Intent.GREETING), ("Namaste!", Intent.GREETING), ("thank you", Intent.THANKS),
     ("live wire sparking on the street", Intent.EMERGENCY), ("garbage not collected", Intent.ISSUE)],
)
def test_detect_intent(text, intent):
    assert detect_intent(text) == intent


# --- Conversation flow -------------------------------------------------------------

def test_requires_login(client):
    assert client.post(CHAT, json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 401


def test_greeting_offers_suggestions(client, tokens, seeded):
    body = chat(client, tokens, "hello")
    assert body["intent"] == "greeting" and body["category"] is None
    assert body["suggestions"] and not body["offices"]


def test_asks_for_location_when_missing(client, tokens, seeded):
    body = chat(client, tokens, "Drainage problem in my area")

    assert body["category"]["slug"] == "drainage-sewerage"
    assert body["needs_location"] is True
    assert body["location_status"] == "not_provided"
    assert "locality or PIN code" in body["reply"]
    # Channels that work from anywhere are still given.
    phones = {c["phone"] for c in body["channels"]}
    assert "155313" in phones
    assert all(o["distance_m"] is None for o in body["offices"])
    assert body["file_complaint"] == {"category_id": seeded["drainage-sewerage"].id}
    assert body["steps"] and "documents" not in body
    assert "cannot guarantee" in body["disclaimer"]


def test_coordinates_give_nearest_offices_with_links(client, tokens, seeded):
    body = chat(client, tokens, "Drainage problem in my area", location=KHAIRATABAD)

    assert body["needs_location"] is False and body["location_status"] == "resolved"
    offices = body["offices"]
    distances = [o["distance_m"] for o in offices if o["distance_m"] is not None]
    assert distances == sorted(distances) and distances
    nearest = offices[0]
    assert nearest["name"] == "HMWSSB Head Office"
    assert nearest["source_type"] == "official" and nearest["source_url"].startswith("https://")
    assert nearest["verified_on"] == "2026-10-10"
    assert nearest["directions_url"].startswith("https://www.google.com/maps/dir/?api=1&destination=")
    # The user's own coordinates never appear in links.
    assert "17.4126" not in nearest["directions_url"] and "17.4126" not in nearest["osm_directions_url"]
    assert "Nearest listed office" in body["reply"]


def test_category_remembered_from_earlier_turn(client, tokens, seeded):
    history = [
        {"role": "user", "content": "power cut in my street since morning"},
        {"role": "assistant", "content": "Please share your location."},
    ]
    body = chat(client, tokens, "I am in Ameerpet", location={"text": "Ameerpet"}, history=history)
    assert body["category"]["slug"] == "electricity"


def test_typed_locality_is_geocoded(client, tokens, seeded, _no_network):
    _no_network.result = GeocodeResult(17.4375, 78.4483, "Ameerpet, Hyderabad")
    body = chat(client, tokens, "no water supply", location={"text": "Ameerpet"})

    assert _no_network.queries == ["Ameerpet"]
    assert body["location_status"] == "resolved"
    assert body["location"]["coordinates_source"] == "OpenStreetMap Nominatim (approximate)"
    assert body["offices"][0]["distance_m"] is not None


def test_pin_in_message_is_used(client, tokens, seeded, _no_network):
    _no_network.result = GeocodeResult(17.4375, 78.4483, "500016")
    body = chat(client, tokens, "street light not working near 500016")
    assert _no_network.queries == ["500016"] and body["location_status"] == "resolved"


def test_geocoder_failure_degrades_gracefully(client, tokens, seeded, _no_network):
    _no_network.error = True
    body = chat(client, tokens, "garbage not collected", location={"text": "Ameerpet"})
    assert body["location_status"] == "unavailable"
    assert body["needs_location"] is False
    assert body["channels"] and all(o["distance_m"] is None for o in body["offices"])
    assert "not available right now" in body["reply"]


def test_unknown_locality(client, tokens, seeded):
    body = chat(client, tokens, "garbage not collected", location={"text": "Xyzzyville"})
    assert body["location_status"] == "not_found"
    assert "couldn't find" in body["reply"]


def test_outside_hyderabad_is_flagged(client, tokens, seeded):
    body = chat(client, tokens, "power cut", location={"latitude": 28.61, "longitude": 77.20})
    assert body["location"]["in_coverage_area"] is False
    assert "outside the Hyderabad area" in body["reply"]


def test_emergency_puts_112_first(client, tokens, seeded):
    body = chat(client, tokens, "live wire sparking near the bus stop")
    assert body["intent"] == "emergency"
    assert body["reply"].startswith("If anyone is in danger")
    assert body["reply"].index("112") < body["reply"].index("1912")


def test_unknown_problem_asks_for_detail(client, tokens, seeded):
    body = chat(client, tokens, "something is wrong")
    assert body["category"] is None and body["suggestions"]
    assert not body["offices"] and not body["channels"]


def test_empty_data_falls_back_honestly(client, tokens, db):
    make_category(db, name="Drainage & Sewerage", slug="drainage-sewerage")
    body = chat(client, tokens, "drain overflowing", location=KHAIRATABAD)

    assert body["category"]["slug"] == "drainage-sewerage"
    assert body["offices"] == [] and body["channels"] == []
    assert body["needs_location"] is False
    assert "don't have verified official contact details" in body["reply"]
    assert not re.search(r"\d{3,}", body["reply"])
    assert "last checked" not in body["disclaimer"]


def test_only_inactive_records_are_not_used(client, tokens, seeded, db):
    db.query(Office).update({Office.is_active: False})
    db.commit()
    body = chat(client, tokens, "power cut")
    assert body["offices"] == [] and body["channels"] == []


# --- Never invent contact details (property-style) ------------------------------

PROMPTS = [
    "Drainage problem in my area", "garbage not collected", "pothole on road", "street light not working",
    "no water supply", "power cut", "stray dogs", "illegal construction", "mosquito breeding",
    "loudspeaker noise", "tree fallen", "I want to complain about something else", "live wire sparking",
    "hello", "kachra pada hai",
]
LOCATIONS = [None, KHAIRATABAD, {"text": "Ameerpet"}, {"latitude": 17.36, "longitude": 78.47}]
_URL = re.compile(r"https?://[^\s)]+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DISTANCE = re.compile(r"\d+(?:\.\d+)?\s?(?:km|m)\b")


def _db_facts(db):
    phones, emails, urls, digits = set(), set(), set(), set()
    for o in db.query(Office).filter_by(is_active=True):
        if o.phone:
            phones.add(o.phone)
        if o.email:
            emails.add(o.email)
        urls.update(u for u in (o.website, o.source_url) if u)
        for text in (o.phone, o.address, o.pincode):
            digits.update(re.sub(r"\D", "", m) for m in re.findall(r"\d[\d\s-]*\d", text or ""))
    return phones, emails, urls, digits


@pytest.mark.parametrize("location", LOCATIONS)
def test_never_returns_contact_details_absent_from_db(client, tokens, seeded, db, location, _no_network):
    _no_network.result = GeocodeResult(17.4375, 78.4483, "Ameerpet")
    phones, emails, urls, digits = _db_facts(db)
    map_hosts = ("https://www.openstreetmap.org/", "https://www.google.com/maps/")

    for prompt in PROMPTS:
        body = chat(client, tokens, prompt, location=location)
        for item in body["offices"] + body["channels"]:
            assert item["phone"] is None or item["phone"] in phones
            assert item["email"] is None or item["email"] in emails
            assert item["website"] is None or item["website"] in urls
            assert item["source_url"] in urls
        text = " ".join([body["reply"], *body["steps"], body["disclaimer"]])
        for email in _EMAIL.findall(text):
            assert email in emails, (prompt, email)
        for url in _URL.findall(text):
            assert url.rstrip(".,") in urls or url.startswith(map_hosts), (prompt, url)
        stripped = _DISTANCE.sub(" ", _EMAIL.sub(" ", _URL.sub(" ", body["reply"])))
        stripped = re.sub(r"\d{1,2} \w{3} \d{4}", " ", stripped)  # verification dates
        for number in re.findall(r"\d[\d\s-]*\d|\d", stripped):
            normalised = re.sub(r"\D", "", number)
            if len(normalised) >= 3:
                assert normalised in digits, (prompt, number)


# --- Gemini grounding ------------------------------------------------------------

def _enable_gemini(monkeypatch, reply, captured=None):
    monkeypatch.setattr(gemini_client, "is_configured", lambda: True)

    def fake_generate(prompt, *, system_instruction=None, temperature=0.2):
        if captured is not None:
            captured.append(prompt)
        return reply

    monkeypatch.setattr(gemini_client, "generate_text", fake_generate)


@pytest.mark.parametrize(
    "invented",
    [
        "For water problems call 1800-425-0000 any time.",
        "Please visit https://hmwssb-complaints.example.com to complain.",
        "Write to help@waterboard.in for a quick fix.",
        "Call 155313 or the office at 040 2999 1234.",
    ],
)
def test_gemini_reply_with_invented_contact_is_rejected(client, tokens, seeded, monkeypatch, invented):
    _enable_gemini(monkeypatch, invented)
    body = chat(client, tokens, "no water supply")
    assert body["generated_by"] == "template"
    assert body["reply"] != invented
    assert "This looks like a Water Supply problem." in body["reply"]
    assert "call 155313" in body["reply"]


def test_grounded_gemini_reply_is_used_without_user_identity(client, tokens, seeded, monkeypatch):
    captured: list[str] = []
    grounded = "Sorry about the water problem. You can call HMWSSB customer care on 155 313 at any time."
    _enable_gemini(monkeypatch, grounded, captured)
    body = chat(client, tokens, "No water supply. I am Lakshmi Reddy, mail me at chat@example.com or 9876543210")

    assert body["generated_by"] == "gemini" and body["reply"] == grounded
    prompt = captured[0]
    assert "chat@example.com" not in prompt and "9876543210" not in prompt
    assert "Lakshmi" not in prompt and "Reddy" not in prompt
    assert "155313" in prompt  # retrieved records are in the prompt


def test_gemini_failure_uses_template(client, tokens, seeded, monkeypatch):
    monkeypatch.setattr(gemini_client, "is_configured", lambda: True)

    def boom(*args, **kwargs):
        raise gemini_client.GeminiUnavailable("down")

    monkeypatch.setattr(gemini_client, "generate_text", boom)
    assert chat(client, tokens, "power cut")["generated_by"] == "template"


def test_gemini_not_called_when_no_records(client, tokens, db, monkeypatch):
    captured: list[str] = []
    _enable_gemini(monkeypatch, "Call 100.", captured)
    make_category(db, name="Water Supply", slug="water-supply")
    body = chat(client, tokens, "no water supply")
    assert captured == [] and body["generated_by"] == "template"


def test_is_grounded_unit():
    from app.schemas.office import OfficeOut

    record = OfficeOut(
        id=1, name="X Helpline", organisation="X", channel_type="helpline", category_slugs=["water-supply"],
        address=None, locality=None, pincode=None, city="Hyderabad", latitude=None, longitude=None,
        coordinates_source=None, phone="1912", email="care@x.gov.in", website="https://x.gov.in/",
        source_url="https://x.gov.in/contact", source_type="official", verified_on="2026-10-10", notes=None,
    )
    assert grounding.is_grounded("Call 1912 or email care@x.gov.in, see x.gov.in", [record], "")
    assert not grounding.is_grounded("Call 1913", [record], "")
    assert not grounding.is_grounded("Email boss@x.gov.in", [record], "")
    assert not grounding.is_grounded("See https://y.gov.in/form", [record], "")
    assert grounding.redact_user_text("me@a.com 98765 43210") == "[email] [number]"


# --- Validation and rate limiting -------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {"messages": []},
        {"messages": [{"role": "user", "content": "x" * 1001}]},
        {"messages": [{"role": "user", "content": "   "}]},
        {"messages": [{"role": "user", "content": "hi"}] * 21},
        {"messages": [{"role": "assistant", "content": "hi"}]},
        {"messages": [{"role": "system", "content": "hi"}]},
        {"messages": [{"role": "user", "content": "hi"}], "location": {"latitude": 17.4}},
        {"messages": [{"role": "user", "content": "hi"}], "location": {"latitude": 17.4, "longitude": 78.4,
                                                                         "text": "Ameerpet"}},
        {"messages": [{"role": "user", "content": "hi"}], "location": {}},
        {"messages": [{"role": "user", "content": "hi"}], "location": {"latitude": 95, "longitude": 78.4}},
    ],
)
def test_rejects_invalid_requests(client, tokens, payload):
    assert client.post(CHAT, json=payload, headers=auth_header(tokens)).status_code == 422


def test_rate_limited(client, tokens, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "chatbot_rate_limit_attempts", 2)
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    codes = [client.post(CHAT, json=payload, headers=auth_header(tokens)).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
