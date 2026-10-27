"""Application settings loaded from environment variables / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Complaint Management System"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://complaints:complaints_dev_password@localhost:5432/complaints"

    # Stored as a comma-separated string so it can be set from a plain env var.
    cors_origins: str = "http://localhost:5173"
    # Used to build links in emails (e.g. password reset).
    frontend_url: str = "http://localhost:5173"

    # --- Authentication -------------------------------------------------
    # Required, no default: the app refuses to start without a secret.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30

    # Attempts allowed per client IP per window on sensitive auth endpoints.
    auth_rate_limit_attempts: int = 5
    auth_rate_limit_window_seconds: int = 60

    # --- Uploads -----------------------------------------------------
    # Relative paths resolve against the backend/ folder.
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5
    max_attachments_per_complaint: int = 3
    # Rejects "decompression bombs": small files that decode to huge bitmaps.
    max_image_pixels: int = 40_000_000

    # --- Image analysis (OpenCV quality checks + YOLOv8n COCO detector) --
    vision_detector_enabled: bool = True
    # Relative paths resolve against the backend/ folder; *.pt files are gitignored.
    vision_weights_dir: str = "app/ai/weights"
    vision_model_file: str = "yolov8n.pt"
    # When the weights file is missing, let ultralytics download it once (needs internet).
    vision_allow_weights_download: bool = True
    vision_confidence_threshold: float = 0.35
    # Images are downscaled so the longer side is at most this many pixels before detection.
    vision_max_image_side: int = 1280
    vision_timeout_seconds: float = 20.0
    # Variance of the Laplacian below this value is reported as blurry (see app/ai/vision/quality.py).
    vision_blur_threshold: float = 100.0
    vision_dark_threshold: float = 50.0
    vision_bright_threshold: float = 215.0

    # --- AI endpoints (image analysis, translation) ------------------------
    ai_rate_limit_attempts: int = 20
    ai_rate_limit_window_seconds: int = 60
    translation_max_chars: int = 5000

    # --- "Continue with Google" sign-in (optional; button hidden when unset) --
    # OAuth 2.0 Web client ID from Google Cloud Console. It is public by design.
    google_client_id: str | None = None

    # --- Google Gemini (optional; features fall back when unset) --------
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 20

    # --- Location guidance chatbot (module 8) ----------------------------
    # OpenStreetMap Nominatim geocoder. Respect its usage policy: max 1 request
    # per second, an identifying User-Agent and (ideally) a contact address.
    geocoding_enabled: bool = True
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "ResolveAI-complaint-system/0.1"
    nominatim_contact_email: str | None = None
    geocoding_timeout_seconds: int = 8
    # Chat messages allowed per client IP per window.
    chatbot_rate_limit_attempts: int = 30
    chatbot_rate_limit_window_seconds: int = 60

    # --- Email (optional; without SMTP, dev mode logs reset links) -------
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    # --- AI / NLP (module 5) ------------------------------------------
    # Relative paths resolve against the backend/ folder.
    ai_artifacts_dir: str = "app/ai/artifacts"
    # Possible duplicates: same category, not closed, filed within the window.
    ai_duplicate_window_days: int = 30
    ai_duplicate_threshold: float = 0.35
    ai_duplicate_max_distance_m: float = 500.0
    ai_duplicate_max_results: int = 5
    # /ai/analyze is called while typing, so it gets its own, more generous limit.
    ai_analyze_rate_limit_attempts: int = 30
    ai_analyze_rate_limit_window_seconds: int = 60

    @field_validator("environment")
    @classmethod
    def _normalise_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosted providers (e.g. Neon, Render) give "postgresql://" or "postgres://" URLs;
        # SQLAlchemy would pick psycopg2 for those, but this app ships psycopg 3.
        value = value.strip()
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def _secret_is_strong(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def vision_weights_path(self) -> Path:
        path = Path(self.vision_weights_dir)
        return (path if path.is_absolute() else BACKEND_DIR / path) / self.vision_model_file


@lru_cache
def get_settings() -> Settings:
    return Settings()
