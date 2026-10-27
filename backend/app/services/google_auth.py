"""Verification of Google ID tokens for "Continue with Google".

The browser gets a signed ID token (JWT) from Google Identity Services and sends
it to the backend. We never trust its contents unverified: the google-auth
library checks Google's signature, the issuer, the expiry and that the token was
issued for OUR client ID (audience).
"""

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ServiceUnavailableError

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None


def is_configured() -> bool:
    return bool(get_settings().google_client_id)


def verify_credential(credential: str) -> GoogleIdentity:
    client_id = get_settings().google_client_id
    if not client_id:
        raise ServiceUnavailableError("Google sign-in is not configured on this server.")

    # Imported lazily so the app starts even where the optional library is missing.
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except ValueError as exc:  # bad signature, wrong audience, expired, malformed
        raise AuthenticationError("Google sign-in failed. Please try again.") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS or not claims.get("sub") or not claims.get("email"):
        raise AuthenticationError("Google sign-in failed. Please try again.")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims["email"]).lower(),
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"),
    )
