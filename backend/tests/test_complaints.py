import re
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Complaint, ComplaintAttachment, UserRole
from tests.conftest import auth_header, login, make_category, make_user
from tests.image_factory import CORRUPT_JPEG, JPEG, PNG

COMPLAINTS = "/api/v1/complaints"
VALID = {
    "subject": "Blocked drain near bus stop",
    "description": "The drain outside the bus stop has been blocked for a week and water is overflowing.",
    "location_text": "Ameerpet Main Road, Hyderabad",
}


@pytest.fixture
def citizen(client, db):
    user = make_user(db, email="citizen@example.com", full_name="Ravi Kumar")
    return user, login(client, "citizen@example.com")


@pytest.fixture
def admin(client, db):
    user = make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    return user, login(client, "admin@example.com")


@pytest.fixture
def category(db):
    return make_category(db)


def submit(client, tokens, category_id, files=None, **overrides):
    data = {**VALID, "category_id": str(category_id), **overrides}
    return client.post(COMPLAINTS, data=data, files=files or [], headers=auth_header(tokens))


# --- Categories --------------------------------------------------------------

def test_categories_list_only_active_with_department(client, db, citizen):
    make_category(db, name="Roads", slug="roads", department="Roads Dept")
    make_category(db, name="Retired", slug="retired", is_active=False)
    response = client.get("/api/v1/categories", headers=auth_header(citizen[1]))
    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Roads"]
    assert response.json()[0]["department"]["name"] == "Roads Dept"


def test_categories_require_login(client):
    assert client.get("/api/v1/categories").status_code == 401


# --- Submission ----------------------------------------------------------------

def test_submit_complaint_generates_reference_routes_department_and_history(client, citizen, category):
    response = submit(client, citizen[1], category.id)
    assert response.status_code == 201, response.text
    body = response.json()

    assert re.fullmatch(rf"CMP-{datetime.now(UTC).year}-\d{{6}}", body["reference_number"])
    assert body["status"] == "submitted"
    # Module 5 stores an AI-predicted priority at submission, marked as such.
    assert body["priority"] is not None and body["priority_source"] == "ai"
    assert body["department"]["name"] == "Sewerage Dept"
    assert body["user"]["full_name"] == "Ravi Kumar"
    assert [h["to_status"] for h in body["history"]] == ["submitted"]
    # Owners cannot move a fresh complaint themselves.
    assert body["allowed_transitions"] == []


def test_submit_with_coordinates_and_incident_time(client, citizen, category):
    incident = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    response = submit(client, citizen[1], category.id, latitude="17.4375", longitude="78.4483", incident_at=incident)
    assert response.status_code == 201, response.text
    assert response.json()["latitude"] == pytest.approx(17.4375)


@pytest.mark.parametrize(
    "overrides",
    [
        {"subject": "Hey"},
        {"description": "too short"},
        {"location_text": "x"},
        {"latitude": "17.4"},  # longitude missing
        {"latitude": "95", "longitude": "78"},
        {"incident_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        {"incident_at": "2026-01-01T10:00:00"},  # no timezone
    ],
)
def test_submit_validates_fields(client, citizen, category, overrides):
    assert submit(client, citizen[1], category.id, **overrides).status_code == 422


def test_submit_rejects_inactive_or_unknown_category(client, db, citizen):
    retired = make_category(db, name="Retired", slug="retired", is_active=False)
    assert submit(client, citizen[1], retired.id).status_code == 400
    assert submit(client, citizen[1], 9999).status_code == 400


def test_submit_requires_login(client, category):
    response = client.post(COMPLAINTS, data={**VALID, "category_id": str(category.id)})
    assert response.status_code == 401


# --- Attachments ---------------------------------------------------------------

def test_submit_with_images_stores_files_by_content_type(client, db, citizen, category, _isolated_uploads):
    files = [
        ("attachments", ("photo.png", PNG, "image/png")),
        ("attachments", ("../../evil name.jpg", JPEG, "application/octet-stream")),
    ]
    response = submit(client, citizen[1], category.id, files=files)
    assert response.status_code == 201, response.text
    attachments = response.json()["attachments"]
    assert [a["content_type"] for a in attachments] == ["image/png", "image/jpeg"]
    # Path components are stripped from client-supplied names.
    assert attachments[1]["original_filename"] == "evil name.jpg"

    stored = db.query(ComplaintAttachment).all()
    assert all((_isolated_uploads / "complaints" / a.stored_filename).is_file() for a in stored)


def test_attachment_with_fake_image_extension_is_rejected(client, db, citizen, category, _isolated_uploads):
    files = [("attachments", ("photo.jpg", b"<script>alert(1)</script>", "image/jpeg"))]
    response = submit(client, citizen[1], category.id, files=files)
    assert response.status_code == 400
    assert "not a supported image" in response.json()["detail"]
    assert db.query(Complaint).count() == 0


def test_attachment_with_valid_header_but_corrupt_body_is_rejected(client, db, citizen, category, _isolated_uploads):
    files = [("attachments", ("photo.jpg", CORRUPT_JPEG, "image/jpeg"))]
    response = submit(client, citizen[1], category.id, files=files)
    assert response.status_code == 400
    assert "could not be read as an image" in response.json()["detail"]
    assert db.query(Complaint).count() == 0
    folder = _isolated_uploads / "complaints"
    assert not folder.exists() or list(folder.iterdir()) == []


def test_bad_second_file_rejects_whole_submission_and_cleans_up(client, db, citizen, category, _isolated_uploads):
    files = [
        ("attachments", ("ok.png", PNG, "image/png")),
        ("attachments", ("bad.gif", b"GIF89a....", "image/gif")),
    ]
    assert submit(client, citizen[1], category.id, files=files).status_code == 400
    assert db.query(Complaint).count() == 0
    folder = _isolated_uploads / "complaints"
    assert not folder.exists() or list(folder.iterdir()) == []


def test_too_many_or_too_large_attachments_are_rejected(client, citizen, category, monkeypatch):
    four = [("attachments", (f"p{i}.png", PNG, "image/png")) for i in range(4)]
    assert submit(client, citizen[1], category.id, files=four).status_code == 400

    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)
    big = [("attachments", ("big.png", PNG, "image/png"))]
    response = submit(client, citizen[1], category.id, files=big)
    assert response.status_code == 400
    assert "larger than" in response.json()["detail"]


def test_attachment_download_is_authorized(client, db, citizen, category):
    created = submit(client, citizen[1], category.id, files=[("attachments", ("p.png", PNG, "image/png"))]).json()
    url = f"{COMPLAINTS}/{created['id']}/attachments/{created['attachments'][0]['id']}"

    own = client.get(url, headers=auth_header(citizen[1]))
    assert own.status_code == 200
    assert own.content == PNG
    assert own.headers["content-type"] == "image/png"
    assert own.headers["x-content-type-options"] == "nosniff"

    make_user(db, email="other@example.com")
    other = login(client, "other@example.com")
    assert client.get(url, headers=auth_header(other)).status_code == 404
    assert client.get(url).status_code == 401


# --- Viewing and privacy -------------------------------------------------------

def test_users_only_see_their_own_complaints(client, db, citizen, category):
    mine = submit(client, citizen[1], category.id).json()
    make_user(db, email="other@example.com")
    other = login(client, "other@example.com")
    theirs = submit(client, other, category.id).json()

    listing = client.get(COMPLAINTS, headers=auth_header(citizen[1])).json()
    assert [c["id"] for c in listing["items"]] == [mine["id"]]

    # Someone else's complaint is reported as missing, by id and by reference.
    assert client.get(f"{COMPLAINTS}/{theirs['id']}", headers=auth_header(citizen[1])).status_code == 404
    ref_url = f"{COMPLAINTS}/reference/{theirs['reference_number']}"
    assert client.get(ref_url, headers=auth_header(citizen[1])).status_code == 404


def test_track_by_reference_is_case_insensitive(client, citizen, category):
    created = submit(client, citizen[1], category.id).json()
    response = client.get(f"{COMPLAINTS}/reference/{created['reference_number'].lower()}", headers=auth_header(citizen[1]))
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_admin_sees_all_complaints_and_can_filter(client, db, citizen, admin, category):
    roads = make_category(db, name="Roads", slug="roads", department="Roads Dept")
    first = submit(client, citizen[1], category.id).json()
    submit(client, citizen[1], roads.id, subject="Pothole on flyover ramp")

    everything = client.get(COMPLAINTS, headers=auth_header(admin[1])).json()
    assert everything["total"] == 2

    by_category = client.get(COMPLAINTS, params={"category_id": roads.id}, headers=auth_header(admin[1])).json()
    assert [c["subject"] for c in by_category["items"]] == ["Pothole on flyover ramp"]

    by_search = client.get(COMPLAINTS, params={"search": first["reference_number"]}, headers=auth_header(admin[1])).json()
    assert [c["id"] for c in by_search["items"]] == [first["id"]]

    mine = client.get(COMPLAINTS, params={"mine": True}, headers=auth_header(admin[1])).json()
    assert mine["total"] == 0


def test_list_pagination_and_sorting(client, citizen, category):
    ids = [submit(client, citizen[1], category.id, subject=f"Complaint number {i}").json()["id"] for i in range(3)]
    page = client.get(COMPLAINTS, params={"limit": 2, "sort": "oldest"}, headers=auth_header(citizen[1])).json()
    assert page["total"] == 3
    assert [c["id"] for c in page["items"]] == ids[:2]


# --- Status lifecycle ----------------------------------------------------------

def move(client, tokens, complaint_id, status, note=None):
    return client.post(f"{COMPLAINTS}/{complaint_id}/status", json={"status": status, "note": note}, headers=auth_header(tokens))


def test_full_lifecycle_with_owner_confirmation(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]

    assert move(client, admin[1], cid, "assigned").status_code == 200
    assert move(client, admin[1], cid, "in_progress").status_code == 200
    resolved = move(client, admin[1], cid, "resolved", "Drain cleared by sanitation crew.")
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None

    owner_view = client.get(f"{COMPLAINTS}/{cid}", headers=auth_header(citizen[1])).json()
    assert owner_view["allowed_transitions"] == ["in_progress", "closed"]

    closed = move(client, citizen[1], cid, "closed")
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == "closed" and body["closed_at"] is not None
    assert [h["to_status"] for h in body["history"]] == ["submitted", "assigned", "in_progress", "resolved", "closed"]
    assert body["history"][3]["note"] == "Drain cleared by sanitation crew."
    assert body["history"][4]["changed_by"]["full_name"] == "Ravi Kumar"


def test_owner_can_reopen_with_reason(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]
    for status, note in [("assigned", None), ("in_progress", None), ("resolved", "Fixed.")]:
        move(client, admin[1], cid, status, note)

    assert move(client, citizen[1], cid, "in_progress").status_code == 400  # reason required
    reopened = move(client, citizen[1], cid, "in_progress", "Water is overflowing again.")
    assert reopened.status_code == 200
    assert reopened.json()["resolved_at"] is None


def test_invalid_and_unauthorized_transitions_are_rejected(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]
    # Skipping stages is not allowed.
    assert move(client, admin[1], cid, "resolved", "Done").status_code == 400
    # Owners cannot drive staff transitions.
    assert move(client, citizen[1], cid, "assigned").status_code == 400
    # Resolving requires a note.
    move(client, admin[1], cid, "assigned")
    move(client, admin[1], cid, "in_progress")
    assert move(client, admin[1], cid, "resolved", "   ").status_code == 400


def test_early_closure_requires_reason_and_closed_is_final(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]
    assert move(client, admin[1], cid, "closed").status_code == 400
    assert move(client, admin[1], cid, "closed", "Duplicate of an existing complaint.").status_code == 200
    assert move(client, admin[1], cid, "in_progress").status_code == 400


def test_other_users_cannot_change_status(client, db, citizen, category):
    cid = submit(client, citizen[1], category.id).json()["id"]
    make_user(db, email="other@example.com")
    other = login(client, "other@example.com")
    assert move(client, other, cid, "closed", "no").status_code == 404


# --- Comments ------------------------------------------------------------------

def comment(client, tokens, complaint_id, body, internal=False):
    return client.post(
        f"{COMPLAINTS}/{complaint_id}/comments", json={"body": body, "is_internal": internal}, headers=auth_header(tokens)
    )


def test_comments_and_internal_notes_visibility(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]

    assert comment(client, citizen[1], cid, "Any update?").status_code == 201
    assert comment(client, admin[1], cid, "Crew scheduled for Monday.").status_code == 201
    assert comment(client, admin[1], cid, "Contractor is slow; escalate.", internal=True).status_code == 201

    owner_view = client.get(f"{COMPLAINTS}/{cid}", headers=auth_header(citizen[1])).json()
    assert [c["body"] for c in owner_view["comments"]] == ["Any update?", "Crew scheduled for Monday."]

    admin_view = client.get(f"{COMPLAINTS}/{cid}", headers=auth_header(admin[1])).json()
    assert len(admin_view["comments"]) == 3
    assert admin_view["comments"][2]["is_internal"] is True


def test_users_cannot_post_internal_notes_or_comment_on_closed(client, citizen, admin, category):
    cid = submit(client, citizen[1], category.id).json()["id"]
    assert comment(client, citizen[1], cid, "secret", internal=True).status_code == 403
    assert comment(client, citizen[1], cid, "   ").status_code == 422

    move(client, admin[1], cid, "closed", "Duplicate.")
    assert comment(client, citizen[1], cid, "Why closed?").status_code == 400
    assert comment(client, admin[1], cid, "See complaint CMP-2026-000001.").status_code == 201
