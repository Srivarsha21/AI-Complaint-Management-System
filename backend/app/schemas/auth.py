"""Authentication request/response schemas."""

from pydantic import BaseModel, Field

from app.schemas.user import FullName, NormalisedEmail, Password, UserOut


class RegisterRequest(BaseModel):
    full_name: FullName
    email: NormalisedEmail
    password: Password


class LoginRequest(BaseModel):
    email: NormalisedEmail
    password: str = Field(max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class AuthResponse(TokenPair):
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=2048)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=2048)


class ForgotPasswordRequest(BaseModel):
    email: NormalisedEmail


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: Password


class MessageResponse(BaseModel):
    message: str


class GoogleLoginRequest(BaseModel):
    # Google ID token (a signed JWT) from Google Identity Services.
    credential: str = Field(min_length=20, max_length=4096)


class AuthConfig(BaseModel):
    google_client_id: str | None
