"""Lightweight intent detection for the guidance conversation."""

import enum
import re


class Intent(str, enum.Enum):
    GREETING = "greeting"
    THANKS = "thanks"
    EMERGENCY = "emergency"
    ISSUE = "issue"  # anything else: treated as a description of a problem


_GREETING = re.compile(
    r"^\s*(hi+|hello+|hey+|namaste|namaskaram|namaskar|good\s+(morning|afternoon|evening)|salaam|"
    r"నమస్కారం|नमस्ते)\b[\s!.,]*$",
    re.IGNORECASE,
)
_THANKS = re.compile(r"^\s*(thanks?|thank\s+you|thx|ok(ay)?\s+thanks?|dhanyavaad|dhanyavadalu|shukriya)\b[\s!.,]*$",
                     re.IGNORECASE)
# Situations where life or property is at immediate risk.
_EMERGENCY = re.compile(
    r"\b(fire|on fire|burning house|electrocut\w*|electric shock|live wire|sparking|short circuit|gas leak\w*|"
    r"accident|injured|bleeding|unconscious|collapsed?|building collapse|drowning|someone fell|"
    r"fell into (a |the )?(manhole|drain)|attack(ed)?|dog bite|bitten)\b",
    re.IGNORECASE,
)


def detect_intent(text: str) -> Intent:
    if _EMERGENCY.search(text or ""):
        return Intent.EMERGENCY
    if _GREETING.match(text or ""):
        return Intent.GREETING
    if _THANKS.match(text or ""):
        return Intent.THANKS
    return Intent.ISSUE
