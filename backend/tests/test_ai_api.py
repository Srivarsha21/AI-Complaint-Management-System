"""Module 5 API and persistence tests: /ai/analyze, prediction on submission, staff views."""

from datetime import UTC, datetime, timedelta

import pytest

from app.ai import classifier
from app.core.config import get_settings
from app.models import (
    AuditLog,
    Complaint,
    ComplaintAIPrediction,
    ComplaintStatus,
    ComplaintStatusHistory,
    UserRole,
)
from app.repositories import ai_repository
from app.services import ai_service
from tests.conftest import auth_header, login, make_category, make_user

ANALYZE = "/api/v1/ai/analyze"
COMPLAINTS = "/api/v1/complaints"
LIVE_WIRE = {
    "subject": "Live wire hanging on road",
    "description": "A live electric wire has fallen on the road near the bus stop in Ameerpet and it is sparking.",
}
GARBAGE = {
    "subject": "Garbage not collected",
    "description": "Garbage has not been collected near the bus stop in Ameerpet for a week, the bin is overflowing.",
}


@pytest.fixture
def citizen(client, db):
    user = make_user(db, email="citizen@example.com", full_name="Ravi Kumar")
    return user, login(client, "citizen@example.com")


@pytest.fixture
def other_citizen(client, db):
    user = make_user(db, email="other@example.com", full_name="Sita Devi")
    return user, login(client, "other@example.com")


@pytest.fixture
def admin(client, db):
    user = make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    return user, login(client, "admin@example.com")


@pytest.fixture
def categories(db):
    """Categories with the real seeded slugs, so model predictions map to them."""
    return {
        "electricity": make_category(db, name="Electricity", slug="electricity", department="Electricity Department"),
        "garbage": make_category(db, name="Garbage & Sanitation", slug="garbage-sanitation", department="Sanitation Department"),
        "lights": make_category(db, name="Street Lights", slug="street-lights", department="Street Lighting Department"),
    }


def submit(client, tokens, category_id, **overrides):
    data = {**GARBAGE, "location_text": "Ameerpet, Hyderabad", "category_id": str(category_id), **overrides}
    response = client.post(COMPLAINTS, data=data, headers=auth_header(tokens))
    assert response.status_code == 201, response.text
    return response.json()


def add_complaint(db, *, user, category, subject, description, status=ComplaintStatus.SUBMITTED,
                  created_at=None, latitude=None, longitude=None) -> Complaint:
    complaint = Complaint(
        user_id=user.id, subject=subject, description=description, category_id=category.id,
        department_id=category.department_id, location_text="Hyderabad", status=status,
        latitude=latitude, longitude=longitude,
    )
    if created_at is not None:
        complaint.created_at = created_at
    db.add(complaint)
    db.flush()
    complaint.reference_number = f"CMP-2026-{complaint.id:06d}"
    db.commit()
    return complaint


# --- /ai/analyze ------------------------------------------------------------------------------

def test_analyze_requires_login(client):
    assert client.post(ANALYZE, json=LIVE_WIRE).status_code == 401


def test_analyze_suggests_category_department_priority_and_emergency(client, citizen, categories):
    response = client.post(ANALYZE, json=LIVE_WIRE, headers=auth_header(citizen[1]))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["model_status"] == "ready"
    assert body["category"]["slug"] == "electricity"
    assert body["category"]["id"] == categories["electricity"].id
    assert 0 < body["category"]["confidence"] <= 1
    assert body["department"]["name"] == "Electricity Department"
    assert all(alt["slug"] != "electricity" for alt in body["alternatives"])
    assert len(body["alternatives"]) <= 3
    assert body["priority"]["level"] == "critical"
    assert any("danger to life" in f for f in body["priority"]["factors"])
    assert body["possible_emergency"] is True
    assert "112" in body["emergency_message"]
    assert body["sentiment"]["label"] in {"negative", "neutral", "positive"}
    assert body["model_version"].startswith("tfidf-logreg-")
    assert "synthetic" in body["disclaimer"]


def test_analyze_validates_input(client, citizen):
    headers = auth_header(citizen[1])
    assert client.post(ANALYZE, json={"description": "short"}, headers=headers).status_code == 422
    bad_coords = {**LIVE_WIRE, "latitude": 17.4}
    assert client.post(ANALYZE, json=bad_coords, headers=headers).status_code == 422
    assert client.post(ANALYZE, json={**LIVE_WIRE, "category_id": 999}, headers=headers).status_code == 400


def test_analyze_duplicates_hide_other_users_details_from_non_staff(client, db, citizen, other_citizen, admin, categories):
    existing = add_complaint(
        db, user=other_citizen[0], category=categories["garbage"], subject="Garbage not collected near bus stop",
        description="Garbage has not been collected near the bus stop in Ameerpet, the bin is overflowing.",
    )
    payload = {**GARBAGE, "category_id": categories["garbage"].id}

    body = client.post(ANALYZE, json=payload, headers=auth_header(citizen[1])).json()
    assert len(body["duplicates"]) == 1
    match = body["duplicates"][0]
    assert match["reference_number"] == existing.reference_number
    assert match["status"] == "submitted"
    assert 0 < match["similarity"] <= 1
    assert match["subject"] is None and match["complaint_id"] is None and match["distance_m"] is None

    staff_match = client.post(ANALYZE, json=payload, headers=auth_header(admin[1])).json()["duplicates"][0]
    assert staff_match["subject"] == existing.subject
    assert staff_match["complaint_id"] == existing.id


def test_analyze_without_trained_model_falls_back(client, citizen, categories, monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "model_path", lambda: tmp_path / "missing.joblib")
    classifier.reset_cache()
    try:
        body = client.post(ANALYZE, json=LIVE_WIRE, headers=auth_header(citizen[1])).json()
    finally:
        monkeypatch.undo()
        classifier.reset_cache()
    assert body["model_status"] == "not_trained"
    assert body["category"] is None and body["alternatives"] == [] and body["model_version"] is None
    # Rules still work without the model.
    assert body["possible_emergency"] is True
    assert body["priority"]["level"] == "critical"


def test_analyze_is_rate_limited_per_ip(client, citizen, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_analyze_rate_limit_attempts", 2)
    headers = auth_header(citizen[1])
    assert client.post(ANALYZE, json=GARBAGE, headers=headers).status_code == 200
    assert client.post(ANALYZE, json=GARBAGE, headers=headers).status_code == 200
    response = client.post(ANALYZE, json=GARBAGE, headers=headers)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


# --- Duplicate candidate query ----------------------------------------------------------------

def test_duplicate_search_respects_category_window_status_geo_and_threshold(db, citizen, categories):
    user = citizen[0]
    text = dict(subject="Garbage not collected near bus stop",
                description="Garbage has not been collected near the bus stop in Ameerpet, the bin is overflowing.")
    near = add_complaint(db, user=user, category=categories["garbage"], latitude=17.4375, longitude=78.4483, **text)
    no_coords = add_complaint(db, user=user, category=categories["garbage"], **text)
    add_complaint(db, user=user, category=categories["garbage"], status=ComplaintStatus.CLOSED, **text)
    add_complaint(db, user=user, category=categories["lights"], **text)
    add_complaint(db, user=user, category=categories["garbage"], created_at=datetime.now(UTC) - timedelta(days=45), **text)
    add_complaint(db, user=user, category=categories["garbage"], latitude=17.50, longitude=78.50, **text)  # ~9 km away
    add_complaint(db, user=user, category=categories["garbage"], subject="Dustbin request",
                  description="Please provide a new dustbin for dry waste in our lane.")

    matches = ai_service._similar(
        db, text=GARBAGE["subject"] + ". " + GARBAGE["description"], category_id=categories["garbage"].id,
        latitude=17.4376, longitude=78.4484,
    )
    assert {m.candidate.id for m in matches} == {near.id, no_coords.id}

    candidates = ai_repository.find_duplicate_candidates(
        db, category_id=categories["garbage"].id, since=datetime.now(UTC) - timedelta(days=30), exclude_id=near.id
    )
    assert near.id not in {c.id for c in candidates}


# --- Prediction stored on submission ----------------------------------------------------------

def test_prediction_is_stored_on_submission_and_priority_marked_as_ai(client, db, citizen, categories):
    body = submit(client, citizen[1], categories["electricity"].id, ai_category_accepted="true", **LIVE_WIRE)
    assert body["priority"] == "critical"
    assert body["priority_source"] == "ai"
    assert body["category"]["id"] == categories["electricity"].id  # the citizen's choice is never changed

    record = db.query(ComplaintAIPrediction).filter_by(complaint_id=body["id"]).one()
    assert record.predicted_category_id == categories["electricity"].id
    assert 0 < record.category_confidence <= 1
    assert record.predicted_priority.value == "critical"
    assert record.possible_emergency is True
    assert record.priority_factors
    assert record.sentiment_label in {"negative", "neutral", "positive"}
    assert record.user_accepted_category is True
    assert record.model_version.startswith("tfidf-logreg-")
    assert record.duplicate_candidates == []


def test_submission_without_ai_field_stores_null_acceptance_and_duplicates(client, db, citizen, categories):
    first = submit(client, citizen[1], categories["garbage"].id)
    second = submit(client, citizen[1], categories["garbage"].id)
    record = db.query(ComplaintAIPrediction).filter_by(complaint_id=second["id"]).one()
    assert record.user_accepted_category is None
    assert [d["reference_number"] for d in record.duplicate_candidates] == [first["reference_number"]]


def test_ai_failure_never_blocks_submission(client, db, citizen, categories, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(ai_service, "record_prediction", broken)
    body = submit(client, citizen[1], categories["garbage"].id)
    assert body["reference_number"]
    assert body["priority"] is None and body["priority_source"] is None
    assert db.query(ComplaintAIPrediction).count() == 0
    assert db.query(Complaint).count() == 1


def test_ai_failure_inside_classifier_never_blocks_submission(client, db, citizen, categories, monkeypatch):
    def broken(_text):
        raise ValueError("bad artifact")

    monkeypatch.setattr(classifier, "predict", broken)
    body = submit(client, citizen[1], categories["garbage"].id)
    assert body["status"] == "submitted"
    assert db.query(ComplaintAIPrediction).count() == 0


# --- Staff analysis view and priority override ------------------------------------------------

def test_staff_can_view_ai_analysis_with_similar_complaints(client, citizen, admin, categories):
    first = submit(client, citizen[1], categories["garbage"].id)
    second = submit(client, citizen[1], categories["garbage"].id)

    response = client.get(f"{COMPLAINTS}/{second['id']}/ai", headers=auth_header(admin[1]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prediction"]["predicted_category"]["slug"] == "garbage-sanitation"
    assert body["prediction"]["priority_factors"]
    assert body["priority_source"] == "ai"
    assert [s["complaint_id"] for s in body["similar"]] == [first["id"]]
    assert body["similar"][0]["subject"] == GARBAGE["subject"]


def test_non_staff_cannot_view_ai_analysis_or_override(client, citizen, categories):
    complaint = submit(client, citizen[1], categories["garbage"].id)
    headers = auth_header(citizen[1])
    assert client.get(f"{COMPLAINTS}/{complaint['id']}/ai", headers=headers).status_code == 403
    response = client.patch(f"{COMPLAINTS}/{complaint['id']}/priority", json={"priority": "low"}, headers=headers)
    assert response.status_code == 403


def test_staff_priority_override_is_recorded_and_audited(client, db, citizen, admin, categories):
    complaint = submit(client, citizen[1], categories["garbage"].id)
    assert complaint["priority_source"] == "ai"

    response = client.patch(
        f"{COMPLAINTS}/{complaint['id']}/priority", json={"priority": "high", "note": "School nearby"},
        headers=auth_header(admin[1]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["priority"] == "high"
    assert body["priority_source"] == "staff"
    note = body["history"][-1]["note"]
    assert "Priority set to High by staff" in note and "AI-predicted" in note and "School nearby" in note
    assert body["history"][-1]["from_status"] == body["history"][-1]["to_status"] == "submitted"

    audit = db.query(AuditLog).filter_by(action="complaint.priority_override").one()
    assert audit.actor_id == admin[0].id
    assert audit.details == {"from": complaint["priority"], "from_source": "ai", "to": "high"}
    assert db.query(ComplaintStatusHistory).count() == 2

    # The stored AI prediction is kept for comparison; the complaint keeps the staff value.
    assert db.query(ComplaintAIPrediction).one().predicted_priority.value == complaint["priority"]


def test_override_unknown_complaint_is_404(client, admin):
    response = client.patch(f"{COMPLAINTS}/999/priority", json={"priority": "low"}, headers=auth_header(admin[1]))
    assert response.status_code == 404


def test_override_rejects_invalid_priority(client, citizen, admin, categories):
    complaint = submit(client, citizen[1], categories["garbage"].id)
    response = client.patch(
        f"{COMPLAINTS}/{complaint['id']}/priority", json={"priority": "urgent"}, headers=auth_header(admin[1])
    )
    assert response.status_code == 422
