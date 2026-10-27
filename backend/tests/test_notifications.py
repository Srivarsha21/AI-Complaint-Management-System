import pytest

from app.models import Notification, User, UserRole
from app.services import notification_service
from tests.conftest import auth_header, login, make_category, make_user

COMPLAINTS = "/api/v1/complaints"
NOTIFICATIONS = "/api/v1/notifications"
VALID = {
    "subject": "Blocked drain near bus stop",
    "description": "The drain outside the bus stop has been blocked for a week and water is overflowing.",
    "location_text": "Ameerpet Main Road, Hyderabad",
}


@pytest.fixture
def setup(client, db):
    category = make_category(db)
    citizen = make_user(db, email="citizen@example.com", full_name="Ravi Kumar")
    make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    staff = []
    for email, name in [("s1@example.com", "Officer One"), ("s2@example.com", "Officer Two")]:
        user = make_user(db, email=email, full_name=name, role=UserRole.STAFF)
        user.department_id = category.department_id
        staff.append(user)
    db.commit()
    tokens = {
        key: auth_header(login(client, email))
        for key, email in [("citizen", "citizen@example.com"), ("admin", "admin@example.com"),
                           ("s1", "s1@example.com"), ("s2", "s2@example.com")]
    }
    complaint = client.post(COMPLAINTS, data={**VALID, "category_id": str(category.id)}, headers=tokens["citizen"]).json()
    return {"tokens": tokens, "complaint": complaint, "citizen": citizen, "staff": staff}


def notes_for(db, user: User) -> list[Notification]:
    db.expire_all()
    return db.query(Notification).filter_by(user_id=user.id).order_by(Notification.id).all()


def test_complainant_notified_of_status_changes_and_staff_comments(client, db, setup):
    cid, ref = setup["complaint"]["id"], setup["complaint"]["reference_number"]
    admin = setup["tokens"]["admin"]

    client.post(f"{COMPLAINTS}/{cid}/status", json={"status": "assigned"}, headers=admin)
    client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": "Crew scheduled."}, headers=admin)
    client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": "Internal only", "is_internal": True}, headers=admin)

    notes = notes_for(db, setup["citizen"])
    assert [n.type for n in notes] == ["status_changed", "comment_added"]
    assert notes[0].message == f"{ref}: status changed to Assigned."
    assert notes[0].complaint_id == cid
    assert notes[1].message == f"{ref}: Admin One added a comment."


def test_department_staff_notified_of_complainant_comments_then_only_assignee(client, db, setup):
    cid = setup["complaint"]["id"]
    s1, s2 = setup["staff"]
    citizen = setup["tokens"]["citizen"]

    client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": "Any update?"}, headers=citizen)
    assert [n.type for n in notes_for(db, s1)] == ["complainant_comment"]
    assert [n.type for n in notes_for(db, s2)] == ["complainant_comment"]
    # Own comments never notify yourself.
    assert notes_for(db, setup["citizen"]) == []

    # s1 assigns s2: s2 is told, the complainant hears about the status change.
    client.post(f"{COMPLAINTS}/{cid}/assign", json={"assignee_id": s2.id}, headers=setup["tokens"]["s1"])
    assert [n.type for n in notes_for(db, s2)] == ["complainant_comment", "assigned"]
    assert [n.type for n in notes_for(db, setup["citizen"])] == ["status_changed"]

    # Once assigned, only the assignee hears about complainant comments.
    client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": "Still blocked."}, headers=citizen)
    assert [n.type for n in notes_for(db, s1)] == ["complainant_comment"]
    assert [n.type for n in notes_for(db, s2)] == ["complainant_comment", "assigned", "complainant_comment"]


def test_reopen_notifies_assignee(client, db, setup):
    cid = setup["complaint"]["id"]
    s1, s2 = setup["staff"]
    admin = setup["tokens"]["admin"]
    client.post(f"{COMPLAINTS}/{cid}/assign", json={"assignee_id": s1.id}, headers=admin)
    client.post(f"{COMPLAINTS}/{cid}/status", json={"status": "in_progress"}, headers=admin)
    client.post(f"{COMPLAINTS}/{cid}/status", json={"status": "resolved", "note": "Cleared."}, headers=admin)

    reopened = client.post(
        f"{COMPLAINTS}/{cid}/status", json={"status": "in_progress", "note": "Blocked again."}, headers=setup["tokens"]["citizen"]
    )
    assert reopened.status_code == 200
    assert [n.type for n in notes_for(db, s1)] == ["assigned", "complaint_reopened"]
    assert notes_for(db, s2) == []


def test_list_mark_read_and_read_all(client, db, setup):
    cid = setup["complaint"]["id"]
    admin, citizen = setup["tokens"]["admin"], setup["tokens"]["citizen"]
    for body in ["One", "Two", "Three"]:
        client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": body}, headers=admin)

    page = client.get(NOTIFICATIONS, params={"limit": 2}, headers=citizen).json()
    assert page["total"] == 3 and page["unread"] == 3 and len(page["items"]) == 2
    newest = page["items"][0]

    marked = client.post(f"{NOTIFICATIONS}/{newest['id']}/read", headers=citizen)
    assert marked.status_code == 200 and marked.json()["is_read"] is True

    unread = client.get(NOTIFICATIONS, params={"unread_only": True}, headers=citizen).json()
    assert unread["total"] == 2 and unread["unread"] == 2
    assert newest["id"] not in [n["id"] for n in unread["items"]]

    assert client.post(f"{NOTIFICATIONS}/read-all", headers=citizen).json() == {"updated": 2}
    assert client.get(NOTIFICATIONS, headers=citizen).json()["unread"] == 0


def test_users_only_touch_their_own_notifications(client, db, setup):
    cid = setup["complaint"]["id"]
    client.post(f"{COMPLAINTS}/{cid}/comments", json={"body": "Hello"}, headers=setup["tokens"]["admin"])
    citizen_note = notes_for(db, setup["citizen"])[0]

    other = setup["tokens"]["s2"]
    assert client.get(NOTIFICATIONS, headers=other).json()["total"] == 0
    assert client.post(f"{NOTIFICATIONS}/{citizen_note.id}/read", headers=other).status_code == 404
    assert client.post(f"{NOTIFICATIONS}/read-all", headers=other).json() == {"updated": 0}
    assert notes_for(db, setup["citizen"])[0].is_read is False
    assert client.get(NOTIFICATIONS).status_code == 401


def test_notification_failure_never_breaks_the_main_action(client, db, setup, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("notification store down")

    monkeypatch.setattr(notification_service.notification_repository, "add", boom)
    cid = setup["complaint"]["id"]
    response = client.post(f"{COMPLAINTS}/{cid}/status", json={"status": "assigned"}, headers=setup["tokens"]["admin"])
    assert response.status_code == 200
    assert response.json()["status"] == "assigned"
    assert db.query(Notification).count() == 0
