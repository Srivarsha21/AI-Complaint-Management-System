"""Unicode-range based language detection for English / Telugu text.

Telugu script occupies the Unicode block U+0C00-U+0C7F. Text is classified by
the share of Telugu letters among all letters; this is a script check, not a
statistical language model (romanised Telugu such as "naaku neellu raavatledu"
is reported as English script).
"""

from typing import Literal

Language = Literal["te", "en", "unknown"]

TELUGU_START = 0x0C00
TELUGU_END = 0x0C7F
# Share of letters that must be Telugu for the text to count as Telugu.
TELUGU_RATIO = 0.3


def is_telugu_char(ch: str) -> bool:
    return TELUGU_START <= ord(ch) <= TELUGU_END


def contains_telugu(text: str) -> bool:
    return any(is_telugu_char(ch) for ch in text)


def detect_language(text: str) -> Language:
    telugu = 0
    latin = 0
    for ch in text:
        if is_telugu_char(ch):
            telugu += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    letters = telugu + latin
    if letters == 0:
        return "unknown"
    if telugu / letters >= TELUGU_RATIO:
        return "te"
    return "en" if latin else "unknown"
