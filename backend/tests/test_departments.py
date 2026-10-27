from app.models import AuditLog, Department, UserRole
from tests.conftest import auth_header, login, make_category, make_user

DEPARTMENTS = "/api/v1/admin/departments"
CATEGORIES = "/api/v1/admin/categories"
USERS = "/api/v1/admin/users"


def _admin(client, db):
    admin = make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    return admin, auth_header(login(client, "admin@example.com"))


def _create_department(client, headers, name="Roads Department", **extra):
    response = client.post(DEPARTMENTS, json={"name": name, **extra}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Access ------------------------------------------------------------------------

def test_department_management_is_admin_only(client, db):
    make_user(db, email="u@example.com")
    headers = auth_header(login(client, "u@example.com"))
    assert client.get(DEPARTMENTS, headers=headers).status_code == 403
    assert client.post(DEPARTMENTS, json={"name": "X Dept"}, headers=headers).status_code == 403
    assert client.get(CATEGORIES, headers=headers).status_code == 403
    assert client.patch(f"{CATEGORIES}/1", json={"name": "Y"}, headers=headers).status_code == 403
    assert client.get(DEPARTMENTS).status_code == 401


# --- Departments ---------------------------------------------------------------------

def test_admin_creates_lists_and_updates_department_with_audit(client, db):
    admin, headers = _admin(client, db)
    created = _create_department(
        client, headers, name="  Roads   Department ", description="Potholes and road repair",
        contact_email="Roads@Example.com",
    )
    assert created["name"] == "Roads Department"
    assert created["contact_email"] == "roads@example.com"
    assert created["is_active"] is True

    updated = client.patch(
        f"{DEPARTMENTS}/{created['id']}", json={"description": "", "contact_email": None}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] is None
    assert updated.json()["contact_email"] is None

    listing = client.get(DEPARTMENTS, headers=headers).json()
    assert [d["name"] for d in listing] == ["Roads Department"]

    created_log = db.query(AuditLog).filter_by(action="admin.department_created").one()
    assert created_log.actor_id == admin.id and created_log.target_id == str(created["id"])
    updated_log = db.query(AuditLog).filter_by(action="admin.department_updated").one()
    assert updated_log.details == {
        "before": {"description": "Potholes and road repair", "contact_email": "roads@example.com"},
        "after": {"description": None, "contact_email": None},
    }


def test_department_name_conflicts_return_409(client, db):
    _, headers = _admin(client, db)
    _create_department(client, headers, name="Roads Department")
    other = _create_department(client, headers, name="Water Board")

    assert client.post(DEPARTMENTS, json={"name": "roads department"}, headers=headers).status_code == 409
    rename = client.patch(f"{DEPARTMENTS}/{other['id']}", json={"name": "Roads Department"}, headers=headers)
    assert rename.status_code == 409


def test_department_validation(client, db):
    _, headers = _admin(client, db)
    assert client.post(DEPARTMENTS, json={"name": "x"}, headers=headers).status_code == 422
    assert client.post(DEPARTMENTS, json={"name": "Valid", "contact_email": "not-an-email"}, headers=headers).status_code == 422
    assert client.patch(f"{DEPARTMENTS}/9999", json={"name": "Nope"}, headers=headers).status_code == 404


def test_cannot_deactivate_department_with_active_categories(client, db):
    _, headers = _admin(client, db)
    category = make_category(db, name="Drainage", slug="drainage", department="Sewerage Dept")
    dept_id = category.department_id

    blocked = client.patch(f"{DEPARTMENTS}/{dept_id}", json={"is_active": False}, headers=headers)
    assert blocked.status_code == 409
    assert "1 active category" in blocked.json()["detail"]

    assert client.patch(f"{CATEGORIES}/{category.id}", json={"is_active": False}, headers=headers).status_code == 200
    allowed = client.patch(f"{DEPARTMENTS}/{dept_id}", json={"is_active": False}, headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["is_active"] is False


# --- Categories ----------------------------------------------------------------------

def test_admin_creates_and_remaps_category_with_audit(client, db):
    admin, headers = _admin(client, db)
    roads = _create_department(client, headers, name="Roads Department")
    ghmc = _create_department(client, headers, name="GHMC Maintenance")

    created = client.post(
        CATEGORIES, json={"name": "Potholes", "slug": "Potholes", "department_id": roads["id"]}, headers=headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["slug"] == "potholes"
    assert body["department"] == {"id": roads["id"], "name": "Roads Department"}

    moved = client.patch(f"{CATEGORIES}/{body['id']}", json={"department_id": ghmc["id"]}, headers=headers)
    assert moved.status_code == 200, moved.text
    assert moved.json()["department"]["name"] == "GHMC Maintenance"

    log = db.query(AuditLog).filter_by(action="admin.category_updated").one()
    assert log.actor_id == admin.id
    assert log.details == {"before": {"department_id": roads["id"]}, "after": {"department_id": ghmc["id"]}}
    assert db.query(AuditLog).filter_by(action="admin.category_created").count() == 1

    # Inactive categories remain visible to admins.
    client.patch(f"{CATEGORIES}/{body['id']}", json={"is_active": False}, headers=headers)
    assert [c["is_active"] for c in client.get(CATEGORIES, headers=headers).json()] == [False]


def test_category_conflicts_and_validation(client, db):
    _, headers = _admin(client, db)
    dept = _create_department(client, headers)
    client.post(CATEGORIES, json={"name": "Potholes", "slug": "potholes", "department_id": dept["id"]}, headers=headers)

    same_name = client.post(CATEGORIES, json={"name": "POTHOLES", "slug": "other", "department_id": dept["id"]}, headers=headers)
    assert same_name.status_code == 409
    same_slug = client.post(CATEGORIES, json={"name": "Road damage", "slug": "potholes", "department_id": dept["id"]}, headers=headers)
    assert same_slug.status_code == 409

    bad_slug = client.post(CATEGORIES, json={"name": "Road damage", "slug": "bad slug!", "department_id": dept["id"]}, headers=headers)
    assert bad_slug.status_code == 422
    unknown_dept = client.post(CATEGORIES, json={"name": "Road damage", "slug": "road-damage", "department_id": 9999}, headers=headers)
    assert unknown_dept.status_code == 400


def test_categories_cannot_map_to_inactive_department(client, db):
    _, headers = _admin(client, db)
    active = _create_department(client, headers, name="Roads Department")
    inactive = _create_department(client, headers, name="Old Department", is_active=False)

    created = client.post(
        CATEGORIES, json={"name": "Potholes", "slug": "potholes", "department_id": inactive["id"]}, headers=headers
    )
    assert created.status_code == 400
    assert "inactive" in created.json()["detail"]

    category = client.post(
        CATEGORIES, json={"name": "Potholes", "slug": "potholes", "department_id": active["id"]}, headers=headers
    ).json()
    remap = client.patch(f"{CATEGORIES}/{category['id']}", json={"department_id": inactive["id"]}, headers=headers)
    assert remap.status_code == 400


def test_remapping_category_only_affects_future_complaints(client, db):
    _, headers = _admin(client, db)
    category = make_category(db, name="Drainage", slug="drainage", department="Sewerage Dept")
    make_user(db, email="citizen@example.com")
    citizen = auth_header(login(client, "citizen@example.com"))
    complaint = {
        "subject": "Blocked drain near bus stop",
        "description": "The drain outside the bus stop has been blocked for a week now.",
        "location_text": "Ameerpet, Hyderabad",
        "category_id": str(category.id),
    }
    first = client.post("/api/v1/complaints", data=complaint, headers=citizen).json()

    water = _create_department(client, headers, name="Water Board")
    client.patch(f"{CATEGORIES}/{category.id}", json={"department_id": water["id"]}, headers=headers)
    second = client.post("/api/v1/complaints", data=complaint, headers=citizen).json()

    assert client.get(f"/api/v1/complaints/{first['id']}", headers=citizen).json()["department"]["name"] == "Sewerage Dept"
    assert second["department"]["name"] == "Water Board"


# --- Staff role management ----------------------------------------------------------

def test_admin_makes_user_staff_of_a_department(client, db):
    admin, headers = _admin(client, db)
    dept = _create_department(client, headers)
    target = make_user(db, email="officer@example.com")

    missing = client.patch(f"{USERS}/{target.id}", json={"role": "staff"}, headers=headers)
    assert missing.status_code == 400
    assert "department" in missing.json()["detail"]

    unknown = client.patch(f"{USERS}/{target.id}", json={"role": "staff", "department_id": 9999}, headers=headers)
    assert unknown.status_code == 400

    made = client.patch(f"{USERS}/{target.id}", json={"role": "staff", "department_id": dept["id"]}, headers=headers)
    assert made.status_code == 200, made.text
    assert made.json()["role"] == "staff"
    assert made.json()["department"] == {"id": dept["id"], "name": "Roads Department"}

    log = db.query(AuditLog).filter_by(action="admin.user_updated").one()
    assert log.details["after"] == {"role": "staff", "is_active": True, "department_id": dept["id"]}

    # The staff member sees their department on their own profile.
    me = client.get("/api/v1/users/me", headers=auth_header(login(client, "officer@example.com"))).json()
    assert me["department"]["id"] == dept["id"]

    # Any non-staff role clears the department.
    demoted = client.patch(f"{USERS}/{target.id}", json={"role": "user"}, headers=headers)
    assert demoted.json()["department"] is None
    assert db.get(Department, dept["id"]) is not None
