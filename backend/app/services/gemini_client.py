"""Thin wrapper around the Google Gemini API (google-genai SDK).

Callers must handle `GeminiUnavailable` and provide a non-AI fallback: the
feature has to keep working when no API key is configured or the API fails.
Never send passwords, tokens, emails or other personal identifiers in prompts.
"""

import logging
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GeminiUnavailable(Exception):
    """Gemini is not configured or the request failed."""


def is_configured() -> bool:
    return bool(get_settings().gemini_api_key)


@lru_cache
def _client():
    from google import genai  # imported lazily: optional dependency at runtime

    settings = get_settings()
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options={"timeout": settings.gemini_timeout_seconds * 1000},
    )


def generate_text(prompt: str, *, system_instruction: str | None = None, temperature: float = 0.2) -> str:
    """Return the model's text reply, or raise GeminiUnavailable."""
    if not is_configured():
        raise GeminiUnavailable("GEMINI_API_KEY is not set")

    from google.genai import types

    try:
        response = _client().models.generate_content(
            model=get_settings().gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=temperature),
        )
    except Exception as exc:  # noqa: BLE001 - any SDK/network error means "unavailable"
        logger.warning("gemini request failed: %s", exc.__class__.__name__)
        raise GeminiUnavailable(str(exc)) from exc

    text = (response.text or "").strip()
    if not text:
        raise GeminiUnavailable("empty response")
    return text
