"""Language detection and the translate-for-review endpoint (Gemini mocked)."""

import pytest

from app.ai.language import contains_telugu, detect_language
from app.core.config import get_settings
from app.services import gemini_client
from app.services.translation_service import UNAVAILABLE
from tests.conftest import auth_header, login, make_user

TRANSLATE = "/api/v1/ai/translate"
TELUGU = "మా వీధిలో మూడు రోజులుగా నీళ్ళు రావడం లేదు"


@pytest.fixture
def tokens(client, db):
    make_user(db, email="citizen@example.com")
    return login(client, "citizen@example.com")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (TELUGU, "te"),
        ("No water supply in our street for three days", "en"),
        (f"Ameerpet: {TELUGU}", "te"),
        ("12345 !!", "unknown"),
        ("", "unknown"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


def test_contains_telugu():
    assert contains_telugu("road " + TELUGU[0])
    assert not contains_telugu("plain English")


def test_translate_returns_503_with_clear_message_without_gemini(client, tokens, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    response = client.post(TRANSLATE, json={"text": TELUGU, "source": "auto", "target": "en"}, headers=auth_header(tokens))
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE


def test_translate_uses_strict_faithful_instruction(client, tokens, monkeypatch):
    captured = {}

    def fake_generate(prompt, *, system_instruction=None, temperature=0.2):
        captured.update(prompt=prompt, system=system_instruction, temperature=temperature)
        return "No water has come in our street for three days"

    monkeypatch.setattr(gemini_client, "generate_text", fake_generate)
    response = client.post(TRANSLATE, json={"text": TELUGU, "source": "auto", "target": "en"}, headers=auth_header(tokens))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "translated_text": "No water has come in our street for three days",
        "source_language": "te",
        "target_language": "en",
        "provider": "gemini",
    }
    assert "Do not add, remove" in captured["system"]
    assert TELUGU in captured["prompt"] and "Telugu text into English" in captured["prompt"]
    assert captured["temperature"] == 0.0


def test_translate_gemini_failure_is_503(client, tokens, monkeypatch):
    def failing(*args, **kwargs):
        raise gemini_client.GeminiUnavailable("network")

    monkeypatch.setattr(gemini_client, "generate_text", failing)
    response = client.post(TRANSLATE, json={"text": TELUGU, "target": "en"}, headers=auth_header(tokens))
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE


def test_translate_validation(client, tokens, monkeypatch):
    monkeypatch.setattr(get_settings(), "translation_max_chars", 10)
    headers = auth_header(tokens)
    assert client.post(TRANSLATE, json={"text": "x" * 11, "target": "te"}, headers=headers).status_code == 400
    assert client.post(TRANSLATE, json={"text": "   ", "target": "en"}, headers=headers).status_code == 422
    assert client.post(TRANSLATE, json={"text": "hi", "target": "fr"}, headers=headers).status_code == 422
    same = client.post(TRANSLATE, json={"text": "hello", "source": "auto", "target": "en"}, headers=headers)
    assert same.status_code == 400


def test_translate_requires_login(client):
    assert client.post(TRANSLATE, json={"text": TELUGU, "target": "en"}).status_code == 401
