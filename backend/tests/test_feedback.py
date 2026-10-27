"""Module 11: feedback after resolution and admin review of AI predictions."""

import csv
import io

import pytest

from app.models import AuditLog, ComplaintAIPrediction, UserRole
from tests.conftest import auth_header, login, make_category, make_user

COMPLAINTS = "/api/v1/complaints"
REVIEW = "/api/v1/admin/ai-review"
VALID = {
    "subject": "Blocked drain near bus stop",
    "description": "The drain outside the bus stop has been blocked for a week and water is overflowing.",
    "location_text": "Ameerpet Main Road, Hyderabad",
}


@pytest.fixture
def setup(client, db):
    category = make_category(db, name="Drainage & Sewerage", slug="drainage-sewerage", department="Sewerage Dept")
    other = make_category(db, name="Roads & Potholes", slug="roads-potholes", department="Roads Dept")
    make_user(db, email="citizen@example.com", full_name="Ravi Kumar")
    make_user(db, email="admin@example.com", role=UserRole.ADMIN)
    citizen, admin = login(client, "citizen@example.com"), login(client, "admin@example.com")
    return category, other, citizen, admin


def file_complaint(client, tokens, category_id, accepted=None):
    data = {**VALID, "category_id": str(category_id)}
    if accepted is not None:
        data["ai_category_accepted"] = str(accepted).lower()
    response = client.post(COMPLAINTS, data=data, headers=auth_header(tokens))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def resolve(client, admin, cid):
    for status, note in (("assigned", None), ("in_progress", None), ("resolved", "Fixed.")):
        assert client.post(f"{COMPLAINTS}/{cid}/status", json={"status": status, "note": note}, headers=auth_header(admin)).status_code == 200


FEEDBACK = {"rating": 4, "resolved_satisfactorily": True, "ai_helpful": False, "comment": "Took a while but fixed."}


# --- Feedback ------------------------------------------------------------------------

def test_feedback_only_after_resolution_and_only_once(client, setup):
    category, _, citizen, admin = setup
    cid = file_complaint(client, citizen, category.id)

    assert client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(citizen)).status_code == 400
    resolve(client, admin, cid)

    created = client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(citizen))
    assert created.status_code == 201
    assert created.json()["rating"] == 4
    assert client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(citizen)).status_code == 409
    assert client.get(f"{COMPLAINTS}/{cid}/feedback", headers=auth_header(admin)).json()["comment"] == "Took a while but fixed."


def test_only_the_complainant_can_give_feedback(client, db, setup):
    category, _, citizen, admin = setup
    cid = file_complaint(client, citizen, category.id)
    resolve(client, admin, cid)
    assert client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(admin)).status_code == 403
    make_user(db, email="other@example.com")
    other = login(client, "other@example.com")
    assert client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(other)).status_code == 404


@pytest.mark.parametrize("rating", [0, 6])
def test_feedback_rating_is_validated(client, setup, rating):
    category, _, citizen, admin = setup
    cid = file_complaint(client, citizen, category.id)
    resolve(client, admin, cid)
    response = client.post(f"{COMPLAINTS}/{cid}/feedback", json={**FEEDBACK, "rating": rating}, headers=auth_header(citizen))
    assert response.status_code == 422


# --- AI review -------------------------------------------------------------------------

def test_review_queue_lists_flagged_predictions_and_records_review(client, db, setup):
    category, other, citizen, admin = setup
    flagged = file_complaint(client, citizen, category.id, accepted=False)  # citizen rejected the suggestion
    file_complaint(client, citizen, category.id, accepted=True)

    queue = client.get(REVIEW, headers=auth_header(admin)).json()
    flagged_items = [i for i in queue["items"] if i["complaint"]["id"] == flagged]
    assert flagged_items and "suggestion_rejected" in flagged_items[0]["signals"]

    prediction_id = flagged_items[0]["prediction_id"]
    reviewed = client.patch(
        f"{REVIEW}/{prediction_id}",
        json={"review_status": "incorrect", "corrected_category_id": other.id, "note": "Actually a road issue."},
        headers=auth_header(admin),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "incorrect"
    assert reviewed.json()["corrected_category"]["name"] == "Roads & Potholes"
    assert db.query(AuditLog).filter_by(action="ai.prediction_reviewed").count() == 1

    # Reviewing does not change the complaint or retrain anything; it is only recorded.
    assert db.query(ComplaintAIPrediction).filter_by(id=prediction_id).one().review_status == "incorrect"


def test_corrected_category_requires_incorrect_status(client, setup):
    category, other, citizen, admin = setup
    file_complaint(client, citizen, category.id, accepted=False)
    pid = client.get(REVIEW, headers=auth_header(admin)).json()["items"][0]["prediction_id"]
    response = client.patch(f"{REVIEW}/{pid}", json={"review_status": "correct", "corrected_category_id": other.id}, headers=auth_header(admin))
    assert response.status_code == 400


def test_corrections_export_and_summary(client, db, setup):
    category, other, citizen, admin = setup
    cid = file_complaint(client, citizen, category.id, accepted=False)
    pid = client.get(REVIEW, headers=auth_header(admin)).json()["items"][0]["prediction_id"]
    client.patch(f"{REVIEW}/{pid}", json={"review_status": "incorrect", "corrected_category_id": other.id}, headers=auth_header(admin))
    resolve(client, admin, cid)
    client.post(f"{COMPLAINTS}/{cid}/feedback", json=FEEDBACK, headers=auth_header(citizen))

    export = client.get(f"{REVIEW}/corrections.csv", headers=auth_header(admin))
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 1
    assert rows[0]["corrected_category"] == "roads-potholes"
    assert "citizen@example.com" not in export.text and "Ravi Kumar" not in export.text

    summary = client.get(f"{REVIEW}/summary", headers=auth_header(admin)).json()
    assert summary["predictions"] == 1
    assert summary["marked_incorrect"] == 1
    assert summary["feedback_count"] == 1
    assert summary["average_rating"] == 4
    assert summary["ai_helpful_rate"] == 0


def test_ai_review_is_admin_only(client, setup):
    _, _, citizen, _ = setup
    assert client.get(REVIEW, headers=auth_header(citizen)).status_code == 403
    assert client.get(f"{REVIEW}/summary", headers=auth_header(citizen)).status_code == 403
    assert client.get(f"{REVIEW}/corrections.csv", headers=auth_header(citizen)).status_code == 403
