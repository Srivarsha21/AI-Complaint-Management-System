"""Text normalisation shared by training and inference (one function, so they never drift apart).

Steps: strip URLs, email addresses and phone numbers (privacy: they must not
become model features or be logged), lowercase, map common Indian-English
shorthand ("pls", "asap"), drop punctuation, collapse whitespace and remove a
small stopword list. Negations ("not", "no", "never") are kept because
"light not working" and "light working" mean different things.
"""

import re

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Indian mobile numbers (+91 / 0 prefix, 10 digits starting 6-9) and other long digit runs.
PHONE_RE = re.compile(r"(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}\b|\b\d{10,}\b")
NON_WORD_RE = re.compile(r"[^a-z0-9\s]")
SPACE_RE = re.compile(r"\s+")

SHORTHAND = {
    "pls": "please", "plz": "please", "plse": "please", "asap": "immediately", "immediatly": "immediately",
    "u": "you", "ur": "your", "govt": "government", "hrs": "hours", "nite": "night", "wat": "what",
    "dept": "department", "thx": "thanks", "frm": "from", "nd": "and", "pblm": "problem", "prob": "problem",
}

STOPWORDS = frozenset(
    """a an the and or but if then so of to in on at by for with from into onto as is are was were be been being
    am do does did this that these those it its i me my we our us you your he she they them their his her
    there here which who whom what when where while also very just only too can could would should will shall
    may might sir madam dear respected hello hi kindly please request regards thank thanks""".split()
)


def redact(text: str) -> str:
    """Remove personal identifiers (URLs, emails, phone numbers) from free text."""
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    return PHONE_RE.sub(" ", text)


def normalise(text: str) -> str:
    """Lowercase, redact and strip punctuation; keeps every word (used by the rule-based modules)."""
    text = redact(text or "").lower()
    text = NON_WORD_RE.sub(" ", text)
    words = [SHORTHAND.get(w, w) for w in SPACE_RE.sub(" ", text).strip().split(" ") if w]
    return " ".join(words)


def clean_text(text: str) -> str:
    """Full preprocessing for the TF-IDF models: normalise, then drop stopwords."""
    return " ".join(w for w in normalise(text).split(" ") if w and w not in STOPWORDS)


def complaint_text(subject: str | None, description: str | None) -> str:
    """How a complaint is turned into one input string (the same format as the dataset's `text`)."""
    subject = (subject or "").strip()
    description = (description or "").strip()
    return f"{subject}. {description}" if subject else description
