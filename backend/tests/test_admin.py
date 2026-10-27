from app.models import AuditLog, UserRole
from tests.conftest import auth_header, login, make_user

USERS = "/api/v1/admin/users"
AUDIT = "/api/v1/admin/audit-logs"


def _admin_tokens(client, db):
    admin = make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    return admin, login(client, "admin@example.com")


def test_regular_user_cannot_access_admin_endpoints(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    assert client.get(USERS, headers=auth_header(tokens)).status_code == 403
    assert client.get(AUDIT, headers=auth_header(tokens)).status_code == 403
    assert client.patch(f"{USERS}/1", json={"role": "admin"}, headers=auth_header(tokens)).status_code == 403


def test_admin_lists_and_searches_users(client, db):
    _, tokens = _admin_tokens(client, db)
    make_user(db, email="ravi@example.com", full_name="Ravi Kumar")
    make_user(db, email="sita@example.com", full_name="Sita Rao")

    everyone = client.get(USERS, headers=auth_header(tokens)).json()
    assert everyone["total"] == 3

    found = client.get(USERS, params={"search": "ravi"}, headers=auth_header(tokens)).json()
    assert [u["email"] for u in found["items"]] == ["ravi@example.com"]

    admins = client.get(USERS, params={"role": "admin"}, headers=auth_header(tokens)).json()
    assert admins["total"] == 1


def test_admin_updates_user_and_change_is_audited(client, db):
    admin, tokens = _admin_tokens(client, db)
    target = make_user(db, email="u@example.com")

    response = client.patch(f"{USERS}/{target.id}", json={"is_active": False}, headers=auth_header(tokens))
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    entry = db.query(AuditLog).filter_by(action="admin.user_updated").one()
    assert entry.actor_id == admin.id
    assert entry.target_id == str(target.id)
    assert entry.details == {
        "before": {"role": "user", "is_active": True, "department_id": None},
        "after": {"role": "user", "is_active": False, "department_id": None},
    }

    logs = client.get(AUDIT, headers=auth_header(tokens)).json()
    assert logs["items"][0]["action"] == "admin.user_updated"


def test_admin_cannot_change_own_account(client, db):
    admin, tokens = _admin_tokens(client, db)
    response = client.patch(f"{USERS}/{admin.id}", json={"role": "user"}, headers=auth_header(tokens))
    assert response.status_code == 400


def test_admin_can_promote_and_demote_other_users(client, db):
    _, tokens = _admin_tokens(client, db)
    other = make_user(db, email="u2@example.com")

    promoted = client.patch(f"{USERS}/{other.id}", json={"role": "admin"}, headers=auth_header(tokens))
    assert promoted.json()["role"] == "admin"
    demoted = client.patch(f"{USERS}/{other.id}", json={"role": "user"}, headers=auth_header(tokens))
    assert demoted.json()["role"] == "user"


def test_demoted_admin_loses_admin_access_immediately(client, db):
    _, tokens = _admin_tokens(client, db)
    other = make_user(db, email="admin2@example.com", role=UserRole.ADMIN)
    other_tokens = login(client, "admin2@example.com")
    assert client.get(USERS, headers=auth_header(other_tokens)).status_code == 200

    client.patch(f"{USERS}/{other.id}", json={"role": "user"}, headers=auth_header(tokens))
    assert client.get(USERS, headers=auth_header(other_tokens)).status_code == 403


def test_update_unknown_user_returns_404(client, db):
    _, tokens = _admin_tokens(client, db)
    assert client.patch(f"{USERS}/9999", json={"is_active": False}, headers=auth_header(tokens)).status_code == 404
