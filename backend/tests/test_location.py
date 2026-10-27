"""Module 8: verified office data, loader, geocoding, distance and office search."""

import copy
import json
from datetime import date

import httpx
import pytest

from app.location import geocoding, maps, office_loader
from app.location.distance import format_distance, haversine_m
from app.location.geocoding import GeocodingUnavailable, NominatimGeocoder
from app.location.office_loader import OfficeDataError, load_file, load_records, validate_records
from app.location.office_search import Point, search
from app.models import Office
from tests.conftest import auth_header, login, make_category, make_user

VALID_RECORD = {
    "name": "Test Head Office",
    "organisation": "Test Corporation",
    "channel_type": "office",
    "category_slugs": ["drainage-sewerage"],
    "address": "1 Test Road, Hyderabad 500001",
    "pincode": "500001",
    "latitude": 17.40,
    "longitude": 78.47,
    "coordinates_source": "OpenStreetMap Nominatim (approximate)",
    "phone": "040-00000000",
    "source_url": "https://example.gov.in/contact",
    "source_type": "official",
    "verified_on": "2026-10-10",
}


def record(**overrides) -> dict:
    data = copy.deepcopy(VALID_RECORD)
    for key, value in overrides.items():
        if value is ...:
            data.pop(key, None)
        else:
            data[key] = value
    return data


# --- Seed data and loader ------------------------------------------------------

def test_bundled_data_file_is_valid_and_fully_sourced():
    records = validate_records(office_loader.read_file())
    assert len(records) >= 10
    for r in records:
        assert str(r.source_url).startswith("https://")
        assert r.verified_on <= date.today()
        if r.latitude is not None:
            assert r.coordinates_source


@pytest.mark.parametrize("missing", ["source_url", "verified_on", "source_type"])
def test_loader_rejects_record_without_provenance(missing):
    with pytest.raises(OfficeDataError) as exc:
        validate_records([record(), record(name="Second Office", **{missing: ...})])
    assert any(missing in problem for problem in exc.value.problems)


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"source_url": "not a url"}, "source_url"),
        ({"coordinates_source": None}, "coordinates_source"),
        ({"longitude": None}, "both"),
        ({"pincode": "50001"}, "pincode"),
        ({"address": None}, "address"),
        ({"verified_on": "2999-01-01"}, "future"),
        ({"category_slugs": ["Bad Slug"]}, "slug"),
    ],
)
def test_loader_rejects_invalid_records(overrides, fragment):
    with pytest.raises(OfficeDataError) as exc:
        validate_records([record(**overrides)])
    assert fragment in " ".join(exc.value.problems)


def test_loader_rejects_duplicates():
    with pytest.raises(OfficeDataError, match="duplicate"):
        validate_records([record(), record()])


def test_loader_upsert_is_idempotent_and_updates(db):
    first = load_records(db, validate_records([record()]))
    assert (first.created, first.updated) == (1, 0)

    again = load_records(db, validate_records([record()]))
    assert (again.created, again.updated, again.unchanged) == (0, 0, 1)

    changed = load_records(db, validate_records([record(phone="040-11111111")]))
    assert changed.updated == 1
    assert db.query(Office).count() == 1
    assert db.query(Office).one().phone == "040-11111111"


def test_loader_can_deactivate_missing(db):
    load_records(db, validate_records([record(), record(name="Old Office")]))
    result = load_records(db, validate_records([record()]), deactivate_missing=True)
    assert result.deactivated == 1
    assert {o.name for o in db.query(Office).filter_by(is_active=True)} == {"Test Head Office"}


def test_cli_rejects_file_without_source_url(tmp_path, capsys):
    from app.scripts.load_offices import main

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"records": [record(source_url=...)]}), encoding="utf-8")
    assert main(["--file", str(bad), "--dry-run"]) == 1
    assert "source_url" in capsys.readouterr().out


def test_loading_bundled_file(db):
    result = load_file(db)
    assert result.created == db.query(Office).count() > 0
    assert load_file(db).created == 0


# --- Distance and maps ---------------------------------------------------------

def test_haversine_known_distances():
    assert haversine_m(17.0, 78.0, 17.0, 78.0) == 0
    # One degree of latitude is about 111.2 km.
    assert haversine_m(17.0, 78.0, 18.0, 78.0) == pytest.approx(111_195, rel=1e-3)
    assert format_distance(840) == "840 m"
    assert format_distance(2345) == "2.3 km"


def test_map_links_use_destination_only():
    assert maps.google_directions_url(17.41, 78.46) == "https://www.google.com/maps/dir/?api=1&destination=17.41%2C78.46"
    assert maps.osm_directions_url(17.41, 78.46) == "https://www.openstreetmap.org/directions?route=%3B17.41%2C78.46"
    assert maps.osm_map_url(17.41, 78.46).startswith("https://www.openstreetmap.org/?mlat=17.41&mlon=78.46#map=17/")


def test_search_orders_offices_by_distance(db):
    load_records(db, validate_records([
        record(name="Far Office", latitude=17.50, longitude=78.50),
        record(name="Near Office", latitude=17.401, longitude=78.471),
        record(name="No Coordinates Office", latitude=None, longitude=None, coordinates_source=None),
        record(name="Helpline", channel_type="helpline", address=None, phone="155313",
               latitude=None, longitude=None, coordinates_source=None),
        record(name="Other Category Office", category_slugs=["electricity"]),
    ]))

    offices, channels = search(db, "drainage-sewerage", Point(17.40, 78.47))

    assert [o.name for o in offices] == ["Near Office", "Far Office", "No Coordinates Office"]
    assert offices[0].distance_m < offices[1].distance_m
    assert offices[2].distance_m is None and offices[2].directions_url is None
    assert offices[0].directions_url.endswith("destination=17.401%2C78.471")
    assert [c.name for c in channels] == ["Helpline"]


def test_search_without_origin_has_no_distance(db):
    load_records(db, validate_records([record()]))
    offices, _ = search(db, "drainage-sewerage")
    assert offices[0].distance_m is None
    assert offices[0].map_url is not None


# --- Geocoding -------------------------------------------------------------------

class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_geocoder(handler, clock=None, **kwargs) -> NominatimGeocoder:
    clock = clock or FakeClock()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return NominatimGeocoder(
        base_url="https://nominatim.example", user_agent="TestAgent/1.0", contact_email="ops@example.com",
        client=client, clock=clock, sleep=clock.sleep, **kwargs,
    )


AMEERPET = [{"lat": "17.4375", "lon": "78.4483", "display_name": "Ameerpet, Hyderabad, Telangana"}]


def test_geocoder_sends_bounded_identified_request_and_caches():
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=AMEERPET)

    geocoder = make_geocoder(handler)
    result = geocoder.geocode("  Ameerpet ")
    assert (result.latitude, result.longitude) == (17.4375, 78.4483)
    assert result.source == geocoding.COORDINATES_SOURCE

    params = requests[0].url.params
    assert params["q"] == "Ameerpet, Hyderabad"
    assert params["bounded"] == "1" and params["viewbox"] and params["countrycodes"] == "in"
    assert requests[0].headers["User-Agent"] == "TestAgent/1.0 (ops@example.com)"

    assert geocoder.geocode("ameerpet") == result  # cached, case-insensitive
    assert len(requests) == 1


def test_geocoder_uses_postalcode_for_pin():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=AMEERPET)

    make_geocoder(handler).geocode("500016")
    assert seen["postalcode"] == "500016" and "q" not in seen


def test_geocoder_throttles_to_one_request_per_second():
    clock = FakeClock()
    geocoder = make_geocoder(lambda r: httpx.Response(200, json=AMEERPET), clock=clock)
    geocoder.geocode("Ameerpet")
    geocoder.geocode("Kukatpally")
    assert clock.sleeps and clock.sleeps[0] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503),
        lambda r: httpx.Response(200, content=b"not json"),
        lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("timed out")),
    ],
)
def test_geocoder_failures_raise_unavailable(handler):
    with pytest.raises(GeocodingUnavailable):
        make_geocoder(handler).geocode("Ameerpet")


def test_geocoder_ignores_results_outside_hyderabad_and_empty():
    delhi = [{"lat": "28.61", "lon": "77.20", "display_name": "Delhi"}]
    assert make_geocoder(lambda r: httpx.Response(200, json=delhi)).geocode("Connaught Place") is None
    assert make_geocoder(lambda r: httpx.Response(200, json=[])).geocode("Nowhere") is None
    assert make_geocoder(lambda r: httpx.Response(200, json=AMEERPET)).geocode("ab") is None  # too short


def test_text_helpers():
    assert geocoding.extract_pincode("drain blocked near 500016 bus stop") == "500016"
    assert geocoding.extract_pincode("call 9876543210") is None
    assert geocoding.normalise_query("Ameerpet <script>!!") == "Ameerpet script"
    assert geocoding.in_hyderabad_region(17.385, 78.4867)
    assert not geocoding.in_hyderabad_region(28.61, 77.20)


def test_disabled_geocoder(monkeypatch):
    with pytest.raises(GeocodingUnavailable):
        geocoding.DisabledGeocoder().geocode("Ameerpet")


# --- Offices endpoint -----------------------------------------------------------

def test_offices_endpoint_sorted_and_requires_login(client, db):
    assert client.get("/api/v1/offices").status_code == 401
    make_user(db, email="map@example.com")
    tokens = login(client, "map@example.com")
    make_category(db, name="Drainage & Sewerage", slug="drainage-sewerage")
    load_records(db, validate_records([
        record(name="Far Office", latitude=17.50, longitude=78.50),
        record(name="Near Office", latitude=17.401, longitude=78.471),
    ]))

    response = client.get(
        "/api/v1/offices", params={"category": "drainage-sewerage", "lat": 17.40, "lng": 78.47},
        headers=auth_header(tokens),
    )
    assert response.status_code == 200
    body = response.json()
    assert [o["name"] for o in body["offices"]] == ["Near Office", "Far Office"]
    assert body["offices"][0]["source_url"] == "https://example.gov.in/contact"

    half = client.get("/api/v1/offices", params={"lat": 17.4}, headers=auth_header(tokens))
    assert half.status_code == 400
