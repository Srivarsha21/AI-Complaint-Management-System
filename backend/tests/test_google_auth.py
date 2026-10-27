"""'Continue with Google' sign-in. Google's verification is mocked: tests never call Google."""

import pytest

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.models import AuditLog, User, UserRole
from app.services import google_auth
from app.services.google_auth import GoogleIdentity
from tests.conftest import auth_header, make_user

GOOGLE = "/api/v1/auth/google"
TOKEN = "x" * 40


@pytest.fixture
def google_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client.apps.googleusercontent.com")


def fake_identity(monkeypatch, **overrides):
    identity = GoogleIdentity(
        **{"sub": "1234567890", "email": "priya@gmail.com", "email_verified": True, "name": "Priya Nair", **overrides}
    )
    monkeypatch.setattr(google_auth, "verify_credential", lambda credential: identity)
    return identity


def test_config_exposes_client_id_only_when_configured(client, monkeypatch):
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": None}
    monkeypatch.setattr(get_settings(), "google_client_id", "abc.apps.googleusercontent.com")
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": "abc.apps.googleusercontent.com"}


def test_not_configured_returns_503(client):
    assert client.post(GOOGLE, json={"credential": TOKEN}).status_code == 503


def test_first_google_sign_in_creates_a_citizen_account(client, db, google_enabled, monkeypatch):
    fake_identity(monkeypatch)
    response = client.post(GOOGLE, json={"credential": TOKEN})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["full_name"] == "Priya Nair"
    assert body["user"]["role"] == "user"
    assert client.get("/api/v1/users/me", headers=auth_header(body)).status_code == 200

    user = db.query(User).filter_by(email="priya@gmail.com").one()
    assert user.google_sub == "1234567890"
    assert db.query(AuditLog).filter_by(action="auth.google_signup").count() == 1

    # Signing in again reuses the same account.
    client.post(GOOGLE, json={"credential": TOKEN})
    assert db.query(User).filter_by(email="priya@gmail.com").count() == 1


def test_existing_email_account_is_linked_not_duplicated(client, db, google_enabled, monkeypatch):
    existing = make_user(db, email="priya@gmail.com", full_name="Priya N", role=UserRole.ADMIN)
    fake_identity(monkeypatch)
    body = client.post(GOOGLE, json={"credential": TOKEN}).json()
    assert body["user"]["id"] == existing.id
    assert body["user"]["role"] == "admin"  # Google sign-in never changes roles
    db.refresh(existing)
    assert existing.google_sub == "1234567890"


def test_unverified_google_email_is_rejected(client, db, google_enabled, monkeypatch):
    make_user(db, email="priya@gmail.com")
    fake_identity(monkeypatch, email_verified=False)
    assert client.post(GOOGLE, json={"credential": TOKEN}).status_code == 401
    assert db.query(User).filter_by(email="priya@gmail.com").one().google_sub is None


def test_invalid_token_is_rejected(client, google_enabled, monkeypatch):
    def reject(credential):
        raise AuthenticationError("Google sign-in failed. Please try again.")

    monkeypatch.setattr(google_auth, "verify_credential", reject)
    assert client.post(GOOGLE, json={"credential": TOKEN}).status_code == 401


def test_disabled_account_cannot_sign_in_with_google(client, db, google_enabled, monkeypatch):
    make_user(db, email="priya@gmail.com", is_active=False)
    fake_identity(monkeypatch)
    assert client.post(GOOGLE, json={"credential": TOKEN}).status_code == 403


def test_real_verifier_rejects_garbage_token(google_enabled):
    """The real google-auth check runs offline for a malformed token and must fail closed."""
    with pytest.raises(AuthenticationError):
        google_auth.verify_credential("not-a-real-google-token-at-all")
