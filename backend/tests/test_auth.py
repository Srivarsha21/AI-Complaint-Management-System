from datetime import UTC, datetime, timedelta

import pytest

from app.core import security
from app.models import AuditLog, PasswordResetToken
from app.services import email_service
from tests.conftest import TEST_PASSWORD, auth_header, login, make_user

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
ME = "/api/v1/users/me"


# --- Registration -----------------------------------------------------------

def test_register_creates_user_and_hashes_password(client, db):
    response = client.post(REGISTER, json={"full_name": "  Ravi   Kumar ", "email": "Ravi@Example.com", "password": "secret123"})
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Ravi Kumar"
    assert body["email"] == "ravi@example.com"
    assert body["role"] == "user"
    assert "password" not in body and "hashed_password" not in body

    from app.repositories.user_repository import get_by_email
    stored = get_by_email(db, "ravi@example.com")
    assert stored.hashed_password != "secret123"
    assert stored.hashed_password.startswith("$argon2")


def test_register_rejects_duplicate_email_case_insensitively(client, db):
    make_user(db, email="dup@example.com")
    response = client.post(REGISTER, json={"full_name": "Dup", "email": "DUP@example.com", "password": "secret123"})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "A User", "email": "not-an-email", "password": "secret123"},
        {"full_name": "A User", "email": "a@example.com", "password": "short1"},
        {"full_name": "A User", "email": "a@example.com", "password": "lettersonly"},
        {"full_name": "A User", "email": "a@example.com", "password": "12345678"},
        {"full_name": " ", "email": "a@example.com", "password": "secret123"},
        {"full_name": "A User", "email": "a@example.com", "password": "a1" * 100},
    ],
)
def test_register_validates_input(client, payload):
    assert client.post(REGISTER, json=payload).status_code == 422


def test_register_cannot_self_assign_admin_role(client):
    response = client.post(
        REGISTER, json={"full_name": "Sneaky", "email": "s@example.com", "password": "secret123", "role": "admin"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


# --- Login --------------------------------------------------------------------

def test_login_returns_tokens_and_user(client, db):
    make_user(db, email="u@example.com", full_name="Priya Sharma")
    body = login(client, "U@example.com")
    assert body["token_type"] == "bearer"
    assert body["user"]["full_name"] == "Priya Sharma"
    assert body["expires_in"] == 30 * 60

    me = client.get(ME, headers=auth_header(body))
    assert me.status_code == 200
    assert me.json()["email"] == "u@example.com"
    assert me.json()["last_login_at"] is not None


def test_login_wrong_password_and_unknown_email_give_same_error(client, db):
    make_user(db, email="u@example.com")
    wrong = client.post(LOGIN, json={"email": "u@example.com", "password": "wrong-pass1"})
    unknown = client.post(LOGIN, json={"email": "nobody@example.com", "password": "wrong-pass1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_disabled_account_is_rejected(client, db):
    make_user(db, email="off@example.com", is_active=False)
    response = client.post(LOGIN, json={"email": "off@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 403


def test_login_is_rate_limited(client, db):
    make_user(db, email="u@example.com")
    statuses = [
        client.post(LOGIN, json={"email": "u@example.com", "password": "bad-pass1"}).status_code for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


# --- Protected routes and tokens ----------------------------------------------

def test_protected_route_requires_token(client):
    response = client.get(ME)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_garbage_and_tampered_tokens_are_rejected(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    tampered = tokens["access_token"][:-4] + ("AAAA" if not tokens["access_token"].endswith("AAAA") else "BBBB")
    assert client.get(ME, headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.get(ME, headers={"Authorization": f"Bearer {tampered}"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    response = client.get(ME, headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert response.status_code == 401


def test_expired_access_token_is_rejected(client, db, monkeypatch):
    user = make_user(db, email="u@example.com")
    monkeypatch.setattr(security.get_settings(), "access_token_expire_minutes", -1)
    expired = security.create_token(user.id, "access")
    assert client.get(ME, headers={"Authorization": f"Bearer {expired.token}"}).status_code == 401


def test_refresh_rotates_tokens_and_old_refresh_token_stops_working(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")

    first = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_tokens = first.json()
    assert client.get(ME, headers=auth_header(new_tokens)).status_code == 200

    reused = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_logout_revokes_access_and_refresh_tokens(client, db):
    make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")

    response = client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]}, headers=auth_header(tokens))
    assert response.status_code == 204
    assert client.get(ME, headers=auth_header(tokens)).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_disabled_user_loses_access_with_existing_token(client, db):
    user = make_user(db, email="u@example.com")
    tokens = login(client, "u@example.com")
    user.is_active = False
    db.commit()
    assert client.get(ME, headers=auth_header(tokens)).status_code == 403


# --- Forgot / reset password --------------------------------------------------

@pytest.fixture
def sent_emails(monkeypatch):
    sent: list[dict] = []

    def fake_send(to, full_name, reset_link, expires_minutes):
        sent.append({"to": to, "link": reset_link})
        return True

    monkeypatch.setattr(email_service, "send_password_reset_email", fake_send)
    return sent


def _token_from(link: str) -> str:
    assert "#token=" in link, "reset token must be in the URL fragment"
    return link.split("#token=", 1)[1]


def test_forgot_password_response_is_identical_for_unknown_email(client, db, sent_emails):
    make_user(db, email="u@example.com")
    known = client.post(FORGOT, json={"email": "u@example.com"})
    unknown = client.post(FORGOT, json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [e["to"] for e in sent_emails] == ["u@example.com"]


def test_reset_password_flow(client, db, sent_emails):
    make_user(db, email="u@example.com")
    old_tokens = login(client, "u@example.com")
    client.post(FORGOT, json={"email": "u@example.com"})
    token = _token_from(sent_emails[0]["link"])

    # Only a hash is stored, never the raw token.
    stored = db.query(PasswordResetToken).one()
    assert stored.token_hash != token
    assert stored.token_hash == security.hash_reset_token(token)

    response = client.post(RESET, json={"token": token, "new_password": "newpass456"})
    assert response.status_code == 204

    assert client.post(LOGIN, json={"email": "u@example.com", "password": TEST_PASSWORD}).status_code == 401
    login(client, "u@example.com", "newpass456")
    # Sessions issued before the reset are signed out.
    assert client.get(ME, headers=auth_header(old_tokens)).status_code == 401
    # The link works only once.
    again = client.post(RESET, json={"token": token, "new_password": "another789"})
    assert again.status_code == 400

    actions = {a.action for a in db.query(AuditLog).all()}
    assert {"auth.password_reset_requested", "auth.password_reset"} <= actions


def test_reset_password_rejects_expired_token(client, db, sent_emails):
    make_user(db, email="u@example.com")
    client.post(FORGOT, json={"email": "u@example.com"})
    token = _token_from(sent_emails[0]["link"])
    stored = db.query(PasswordResetToken).one()
    stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    response = client.post(RESET, json={"token": token, "new_password": "newpass456"})
    assert response.status_code == 400


def test_new_reset_request_invalidates_previous_link(client, db, sent_emails):
    make_user(db, email="u@example.com")
    client.post(FORGOT, json={"email": "u@example.com"})
    client.post(FORGOT, json={"email": "u@example.com"})
    first, second = (_token_from(e["link"]) for e in sent_emails)

    assert client.post(RESET, json={"token": first, "new_password": "newpass456"}).status_code == 400
    assert client.post(RESET, json={"token": second, "new_password": "newpass456"}).status_code == 204


def test_reset_password_rejects_unknown_token(client):
    response = client.post(RESET, json={"token": "x" * 43, "new_password": "newpass456"})
    assert response.status_code == 400
