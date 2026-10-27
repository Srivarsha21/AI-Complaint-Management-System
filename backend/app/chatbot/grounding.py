"""Optional Gemini rephrasing, strictly grounded in retrieved records.

Gemini only rewrites the template reply in friendlier words. The prompt holds
the retrieved records and the template; the answer is then checked and
discarded if it contains any phone number, URL or email address that is not
present in those records or the template. No user identity is sent: only the
user's latest problem description, with emails and phone numbers redacted.
"""

import json
import logging
import re

from app.schemas.office import OfficeOut
from app.services import gemini_client

logger = logging.getLogger(__name__)

MAX_REPLY_CHARS = 1500

SYSTEM_INSTRUCTION = (
    "You are a civic complaint guidance assistant for Hyderabad, India. You rewrite a DRAFT reply so it is "
    "clear, polite and concise. Rules: use ONLY facts from DRAFT and RECORDS; never add phone numbers, "
    "websites, email addresses, office names, addresses, distances, timings, fees, documents or procedures "
    "that are not in them; never promise that an office will accept or resolve a complaint; keep every "
    "phone number, URL and email exactly as written; plain text only, no markdown; reply in the same "
    "language as the USER MESSAGE when possible, otherwise English; at most 120 words."
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+|\b[\w-]+(?:\.[\w-]+)*\.(?:gov\.in|org|com|in|net|io)\b[^\s<>\"')\]]*",
                     re.IGNORECASE)
_NUMBER_RE = re.compile(r"\+?\d[\d\s().-]*\d|\d")
_PHONE_LIKE_USER = re.compile(r"\+?\d[\d\s-]{6,}\d")


def redact_user_text(text: str, identity_terms: list[str] | None = None) -> str:
    """Strip personal identifiers (emails, phone numbers, the account's own name) before text leaves the server."""
    for term in sorted((t for t in identity_terms or [] if t and len(t.strip()) >= 2), key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(term.strip())}(?!\w)", "[name]", text, flags=re.IGNORECASE)
    text = _EMAIL_RE.sub("[email]", text)
    return _PHONE_LIKE_USER.sub("[number]", text)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _norm_url(url: str) -> str:
    url = url.strip().rstrip(".,;:!?").lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def allowed_facts(records: list[OfficeOut], template_reply: str) -> tuple[set[str], set[str], set[str]]:
    """(digit strings, normalised URLs, emails) that a reply may mention."""
    texts = [template_reply]
    urls: set[str] = set()
    emails: set[str] = set()
    for r in records:
        texts += [r.phone or "", r.address or "", r.pincode or "", r.name, r.organisation]
        if r.distance_m is not None:
            texts.append(str(r.distance_m))
        for url in (r.website, r.source_url, r.map_url, r.directions_url, r.osm_directions_url):
            if url:
                urls.add(_norm_url(url))
        if r.email:
            emails.add(r.email.lower())
    for match in _URL_RE.findall(template_reply):
        urls.add(_norm_url(match))
    emails.update(e.lower() for e in _EMAIL_RE.findall(template_reply))
    digits: set[str] = set()
    for text in texts:
        for match in _NUMBER_RE.findall(text):
            digits.add(_digits(match))
    return digits, urls, emails


def is_grounded(reply: str, records: list[OfficeOut], template_reply: str) -> bool:
    """True if every phone-like number, URL and email in `reply` is in the records/template."""
    allowed_digits, allowed_urls, allowed_emails = allowed_facts(records, template_reply)

    for email in _EMAIL_RE.findall(reply):
        if email.lower() not in allowed_emails:
            return False
    without_emails = _EMAIL_RE.sub(" ", reply)

    for url in _URL_RE.findall(without_emails):
        normalised = _norm_url(url)
        if not any(normalised == a or a.startswith(normalised) for a in allowed_urls):
            return False
    without_urls = _URL_RE.sub(" ", without_emails)

    for match in _NUMBER_RE.findall(without_urls):
        digits = _digits(match)
        # Short numbers (counts like "2", "24x7") are harmless; 3+ digits could be a phone number.
        if len(digits) >= 3 and digits not in allowed_digits:
            return False
    return True


def rephrase(
    template_reply: str, records: list[OfficeOut], user_message: str, *, identity_terms: list[str] | None = None
) -> str | None:
    """Gemini's grounded rewrite of `template_reply`, or None to keep the template."""
    if not gemini_client.is_configured():
        return None
    facts = [
        {
            "name": r.name,
            "organisation": r.organisation,
            "type": r.channel_type.value,
            "address": r.address,
            "phone": r.phone,
            "email": r.email,
            "website": r.website,
            "distance_m": r.distance_m,
        }
        for r in records
    ]
    prompt = (
        f"USER MESSAGE:\n{redact_user_text(user_message, identity_terms)[:500]}\n\n"
        f"RECORDS (verified official data):\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"DRAFT:\n{template_reply}\n\nRewrite the DRAFT following the rules."
    )
    try:
        reply = gemini_client.generate_text(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.2)
    except gemini_client.GeminiUnavailable:
        return None
    reply = reply.strip()
    if not reply or len(reply) > MAX_REPLY_CHARS:
        return None
    if not is_grounded(reply, records, template_reply):
        logger.warning("discarded ungrounded chatbot reply from Gemini")
        return None
    return reply
