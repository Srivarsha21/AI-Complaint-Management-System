import pytest

from app.models import AuditLog, Category, Department, User, UserRole
from tests.conftest import auth_header, login, make_category, make_user

COMPLAINTS = "/api/v1/complaints"
VALID = {
    "subject": "Blocked drain near bus stop",
    "description": "The drain outside the bus stop has been blocked for a week and water is overflowing.",
    "location_text": "Ameerpet Main Road, Hyderabad",
}


def make_staff(db, email: str, department: Department, *, is_active: bool = True, full_name: str = "Staff Member") -> User:
    user = make_user(db, email=email, full_name=full_name, role=UserRole.STAFF, is_active=is_active)
    user.department_id = department.id
    db.commit()
    return user


@pytest.fixture
def world(client, db):
    """Two departments, a staff member in each, a citizen, an admin and one complaint per department."""
    drainage: Category = make_category(db, name="Drainage", slug="drainage", department="Sewerage Dept")
    roads: Category = make_category(db, name="Roads", slug="roads", department="Roads Dept")
    sewerage_dept, roads_dept = drainage.department, roads.department

    make_user(db, email="citizen@example.com", full_name="Ravi Kumar")
    make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    sew_staff = make_staff(db, "sew@example.com", sewerage_dept, full_name="Sewer Officer")
    sew_staff2 = make_staff(db, "sew2@example.com", sewerage_dept, full_name="Second Sewer Officer")
    road_staff = make_staff(db, "road@example.com", roads_dept, full_name="Road Officer")

    tokens = {
        name: auth_header(login(client, email))
        for name, email in [
            ("citizen", "citizen@example.com"), ("admin", "admin@example.com"),
            ("sew", "sew@example.com"), ("road", "road@example.com"),
        ]
    }
    drain_complaint = client.post(
        COMPLAINTS, data={**VALID, "category_id": str(drainage.id)}, headers=tokens["citizen"]
    ).json()
    road_complaint = client.post(
        COMPLAINTS, data={**VALID, "subject": "Pothole on flyover", "category_id": str(roads.id)}, headers=tokens["citizen"]
    ).json()
    return {
        "tokens": tokens, "sewerage": sewerage_dept, "roads": roads_dept,
        "sew_staff": sew_staff, "sew_staff2": sew_staff2, "road_staff": road_staff,
        "drain": drain_complaint, "road": road_complaint, "drainage_category_id": drainage.id,
    }


def assign(client, headers, complaint_id, **body):
    return client.post(f"{COMPLAINTS}/{complaint_id}/assign", json=body, headers=headers)


# --- Visibility -----------------------------------------------------------------------

def test_staff_only_see_their_departments_complaints(client, world):
    sew, road = world["tokens"]["sew"], world["tokens"]["road"]
    drain_id, road_id = world["drain"]["id"], world["road"]["id"]

    listing = client.get(COMPLAINTS, headers=sew).json()
    assert [c["id"] for c in listing["items"]] == [drain_id]
    assert client.get(f"{COMPLAINTS}/{road_id}", headers=sew).status_code == 404
    ref = world["road"]["reference_number"]
    assert client.get(f"{COMPLAINTS}/reference/{ref}", headers=sew).status_code == 404

    detail = client.get(f"{COMPLAINTS}/{drain_id}", headers=sew).json()
    assert detail["can_manage"] is True
    assert detail["allowed_transitions"] == ["assigned", "closed"]

    assert [c["id"] for c in client.get(COMPLAINTS, headers=road).json()["items"]] == [road_id]
    # `mine` narrows staff to complaints they filed themselves.
    assert client.get(COMPLAINTS, params={"mine": True}, headers=sew).json()["total"] == 0


def test_staff_without_department_see_nothing(client, db, world):
    make_user(db, email="loose@example.com", role=UserRole.STAFF)
    loose = auth_header(login(client, "loose@example.com"))
    assert client.get(COMPLAINTS, headers=loose).json() == {"items": [], "total": 0}
    assert client.get(f"{COMPLAINTS}/{world['drain']['id']}", headers=loose).status_code == 404


def test_staff_transitions_and_internal_notes_limited_to_own_department(client, world):
    sew, road = world["tokens"]["sew"], world["tokens"]["road"]
    drain_id = world["drain"]["id"]

    assert client.post(f"{COMPLAINTS}/{drain_id}/status", json={"status": "assigned"}, headers=sew).status_code == 200
    assert client.post(f"{COMPLAINTS}/{drain_id}/status", json={"status": "in_progress"}, headers=road).status_code == 404

    note = client.post(f"{COMPLAINTS}/{drain_id}/comments", json={"body": "Crew booked", "is_internal": True}, headers=sew)
    assert note.status_code == 201
    assert client.post(f"{COMPLAINTS}/{drain_id}/comments", json={"body": "x", "is_internal": True}, headers=road).status_code == 404

    owner_view = client.get(f"{COMPLAINTS}/{drain_id}", headers=world["tokens"]["citizen"]).json()
    assert owner_view["comments"] == []
    assert owner_view["can_manage"] is False


def test_staff_who_file_complaints_elsewhere_are_treated_as_owners(client, world):
    road = world["tokens"]["road"]
    created = client.post(COMPLAINTS, data={**VALID, "category_id": str(world["drainage_category_id"])}, headers=road).json()
    detail = client.get(f"{COMPLAINTS}/{created['id']}", headers=road).json()
    assert detail["can_manage"] is False
    assert detail["allowed_transitions"] == []
    assert client.post(f"{COMPLAINTS}/{created['id']}/comments", json={"body": "x", "is_internal": True}, headers=road).status_code == 403


# --- Assignment -------------------------------------------------------------------------

def test_staff_assigns_colleague_and_complaint_moves_to_assigned(client, db, world):
    sew = world["tokens"]["sew"]
    drain_id = world["drain"]["id"]
    colleague = world["sew_staff2"]

    response = assign(client, sew, drain_id, assignee_id=colleague.id, note="Area crew lead")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "assigned"
    assert body["assigned_to"]["full_name"] == "Second Sewer Officer"
    assert [h["to_status"] for h in body["history"]] == ["submitted", "assigned"]
    assert body["history"][1]["note"] == "Area crew lead"
    assert len(body["assignments"]) == 1
    entry = body["assignments"][0]
    assert entry["assigned_to"]["id"] == colleague.id
    assert entry["assigned_by"]["full_name"] == "Sewer Officer"
    assert entry["from_department"] == entry["to_department"] == {"id": world["sewerage"].id, "name": "Sewerage Dept"}

    assert db.query(AuditLog).filter_by(action="complaint.assigned").count() == 1

    # The complainant sees who is handling it, but not the internal routing history.
    owner_view = client.get(f"{COMPLAINTS}/{drain_id}", headers=world["tokens"]["citizen"]).json()
    assert owner_view["assigned_to"]["id"] == colleague.id
    assert owner_view["assignments"] == []

    # Re-assigning later does not touch the status again.
    again = assign(client, sew, drain_id, assignee_id=world["sew_staff"].id).json()
    assert again["status"] == "assigned"
    assert len(again["history"]) == 2
    assert len(again["assignments"]) == 2


def test_assignment_validation(client, db, world):
    sew, admin = world["tokens"]["sew"], world["tokens"]["admin"]
    drain_id = world["drain"]["id"]
    inactive = make_staff(db, "gone@example.com", world["sewerage"], is_active=False)
    citizen_user = db.query(User).filter_by(email="citizen@example.com").one()

    # Assignee from another department.
    wrong_dept = assign(client, admin, drain_id, assignee_id=world["road_staff"].id)
    assert wrong_dept.status_code == 400
    assert "department" in wrong_dept.json()["detail"]
    # Non-staff and inactive assignees.
    assert assign(client, admin, drain_id, assignee_id=citizen_user.id).status_code == 400
    assert assign(client, admin, drain_id, assignee_id=inactive.id).status_code == 400
    assert assign(client, admin, drain_id, assignee_id=9999).status_code == 400
    # Body must say what to change.
    assert assign(client, admin, drain_id).status_code == 422
    # Nothing failed half-way.
    detail = client.get(f"{COMPLAINTS}/{drain_id}", headers=sew).json()
    assert detail["status"] == "submitted" and detail["assigned_to"] is None and detail["assignments"] == []


def test_only_managers_can_assign(client, world):
    drain_id = world["drain"]["id"]
    colleague = world["sew_staff2"].id
    # The complainant can see the complaint but cannot assign it.
    assert assign(client, world["tokens"]["citizen"], drain_id, assignee_id=colleague).status_code == 403
    # Staff of another department cannot even see it.
    assert assign(client, world["tokens"]["road"], drain_id, assignee_id=colleague).status_code == 404


def test_staff_cannot_reroute_but_admin_can(client, world):
    sew, admin = world["tokens"]["sew"], world["tokens"]["admin"]
    drain_id = world["drain"]["id"]
    roads_id = world["roads"].id

    denied = assign(client, sew, drain_id, department_id=roads_id)
    assert denied.status_code == 403

    # Assign first, then re-route: the old assignee belongs to the old department and is dropped.
    assign(client, admin, drain_id, assignee_id=world["sew_staff"].id)
    rerouted = assign(client, admin, drain_id, department_id=roads_id, note="Road surface issue, not drainage")
    assert rerouted.status_code == 200, rerouted.text
    body = rerouted.json()
    assert body["department"]["name"] == "Roads Dept"
    assert body["assigned_to"] is None
    assert body["assignments"][-1]["from_department"]["name"] == "Sewerage Dept"
    assert body["assignments"][-1]["to_department"]["name"] == "Roads Dept"

    # Visibility follows the new department.
    assert client.get(f"{COMPLAINTS}/{drain_id}", headers=sew).status_code == 404
    road_view = client.get(f"{COMPLAINTS}/{drain_id}", headers=world["tokens"]["road"])
    assert road_view.status_code == 200

    # Re-route and assign in one step.
    back = assign(client, admin, drain_id, department_id=world["sewerage"].id, assignee_id=world["sew_staff2"].id)
    assert back.status_code == 200
    assert back.json()["assigned_to"]["id"] == world["sew_staff2"].id


def test_reroute_to_inactive_department_rejected(client, db, world):
    admin = world["tokens"]["admin"]
    closed_dept = Department(name="Closed Dept", is_active=False)
    db.add(closed_dept)
    db.commit()
    response = assign(client, admin, world["drain"]["id"], department_id=closed_dept.id)
    assert response.status_code == 400


def test_closed_complaints_cannot_be_assigned(client, world):
    admin = world["tokens"]["admin"]
    drain_id = world["drain"]["id"]
    client.post(f"{COMPLAINTS}/{drain_id}/status", json={"status": "closed", "note": "Duplicate."}, headers=admin)
    assert assign(client, admin, drain_id, assignee_id=world["sew_staff"].id).status_code == 400


def test_department_staff_lookup(client, db, world):
    sew, admin, citizen = world["tokens"]["sew"], world["tokens"]["admin"], world["tokens"]["citizen"]
    make_staff(db, "gone@example.com", world["sewerage"], is_active=False)
    url = f"/api/v1/departments/{world['sewerage'].id}/staff"

    names = [u["full_name"] for u in client.get(url, headers=admin).json()]
    assert names == ["Second Sewer Officer", "Sewer Officer"]  # active only, sorted
    assert client.get(url, headers=sew).status_code == 200
    assert client.get(f"/api/v1/departments/{world['roads'].id}/staff", headers=sew).status_code == 403
    assert client.get(url, headers=citizen).status_code == 403
    assert client.get("/api/v1/departments/9999/staff", headers=admin).status_code == 404
