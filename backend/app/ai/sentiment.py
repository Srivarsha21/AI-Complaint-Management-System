"""Lexicon-based sentiment and urgency scoring (no external model or package).

Method: count positive and negative lexicon words in the normalised text,
flipping a word's polarity when one of the previous two words is a negation
("not good" -> negative) and weighting it 1.5x after an intensifier ("very bad").

    score = (positive - negative) / (positive + negative + 2)       in (-1, 1)
    label = negative if score <= -0.2, positive if score >= 0.2, else neutral

Urgency (0..1) is separate: urgency words ("urgent", "immediately", "danger"),
repeated exclamation marks and SHOUTED words each add a fixed amount.

Limitations (also in docs/ai_dataset.md):
  * Complaints are almost always negative, so the label alone carries little information.
  * Sarcasm, Telugu/Hindi words and mixed-language text are not understood.
  * The lexicon was written by hand for this project; it has NOT been validated
    against human-labelled data, so no accuracy figure is claimed.
"""

from dataclasses import dataclass

from app.ai.preprocessing import normalise

NEGATIVE = frozenset(
    """bad worst terrible horrible pathetic poor dirty filthy stinking smell smelly unbearable suffering suffer
    problem problems issue damaged broken dangerous danger unsafe risk scared afraid angry frustrated disappointed
    useless careless negligence ignored ignoring nobody nothing complaint complained sick ill injured hurt dying
    dead died death disgusting worse waste wasted harassment rude delay delayed pending blocked overflowing
    leaking leakage not_working failed failure fear helpless trouble difficult difficulty""".split()
)
POSITIVE = frozenset(
    """good great thanks thank appreciate appreciated excellent quick quickly fixed resolved solved happy
    satisfied helpful nice clean better best wonderful prompt kind""".split()
)
NEGATIONS = frozenset({"not", "no", "never", "nobody", "without", "nothing"})
INTENSIFIERS = frozenset({"very", "extremely", "too", "so", "really", "highly", "totally", "completely"})
URGENCY = {
    "urgent": 0.3, "urgently": 0.3, "immediately": 0.25, "emergency": 0.35, "danger": 0.25, "dangerous": 0.25,
    "help": 0.15, "now": 0.1, "quickly": 0.1, "fast": 0.1, "today": 0.1, "asap": 0.25, "die": 0.3,
    "life": 0.2, "critical": 0.25, "serious": 0.15, "risk": 0.15,
}


@dataclass(frozen=True)
class SentimentResult:
    label: str  # negative | neutral | positive
    score: float  # -1..1
    urgency: float  # 0..1


def analyse(text: str) -> SentimentResult:
    words = normalise(text).split()
    # Treat "not working" as one negative token: very common in complaints.
    joined: list[str] = []
    for i, w in enumerate(words):
        if w == "working" and i > 0 and words[i - 1] == "not":
            joined[-1] = "not_working"
        else:
            joined.append(w)

    positive = negative = 0.0
    for i, word in enumerate(joined):
        polarity = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if polarity == 0:
            continue
        window = joined[max(0, i - 2):i]
        if word != "not_working" and any(w in NEGATIONS for w in window):
            polarity = -polarity
        weight = 1.5 if window and window[-1] in INTENSIFIERS else 1.0
        if polarity > 0:
            positive += weight
        else:
            negative += weight

    score = (positive - negative) / (positive + negative + 2)
    label = "negative" if score <= -0.2 else "positive" if score >= 0.2 else "neutral"

    urgency = sum(URGENCY.get(w, 0.0) for w in set(joined))
    raw = text or ""
    urgency += min(0.2, 0.05 * raw.count("!"))
    shouted = [w for w in raw.split() if len(w) >= 4 and w.isalpha() and w.isupper()]
    urgency += min(0.2, 0.1 * len(shouted))
    return SentimentResult(label=label, score=round(score, 3), urgency=round(min(1.0, urgency), 3))
