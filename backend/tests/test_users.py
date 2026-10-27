from app.models import AuditLog
from tests.conftest import TEST_PASSWORD, auth_header, login, make_user

ME = "/api/v1/users/me"
CHANGE_PASSWORD = "/api/v1/users/me/change-password"


def test_update_profile_full_name(client, db):
    make_user(db, email="u@example.com", full_name="Old Name")
    tokens = login(client, "u@example.com")
    response = client.patch(ME, json={"full_name": "  Lakshmi   Devi "}, headers=auth_header(tokens))
    assert response.status_code == 200
    assert response.json()["full_name"] == "Lakshmi Devi"


def test_update_profile_ignores_role_and_email_fields(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    response = client.patch(
        ME, json={"full_name": "New Name", "role": "admin", "email": "x@example.com"}, headers=auth_header(tokens)
    )
    assert response.status_code == 200
    assert response.json()["role"] == "user"
    assert response.json()["email"] == "u@example.com"


def test_change_password_signs_out_old_sessions_and_returns_new_tokens(client, db):
    make_user(db, email="u@example.com")
    old = login(client, "u@example.com")

    response = client.post(
        CHANGE_PASSWORD,
        json={"current_password": TEST_PASSWORD, "new_password": "brandNew99"},
        headers=auth_header(old),
    )
    assert response.status_code == 200
    new = response.json()

    assert client.get(ME, headers=auth_header(old)).status_code == 401
    assert client.get(ME, headers=auth_header(new)).status_code == 200
    login(client, "u@example.com", "brandNew99")
    assert db.query(AuditLog).filter_by(action="auth.password_changed").count() == 1


def test_change_password_requires_correct_current_password(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    response = client.post(
        CHANGE_PASSWORD,
        json={"current_password": "wrongpass1", "new_password": "brandNew99"},
        headers=auth_header(tokens),
    )
    assert response.status_code == 400
