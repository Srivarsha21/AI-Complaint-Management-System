"""Explainable, rules-based priority baseline and emergency keyword check.

The priority is a PREDICTION to help staff triage; staff can override it. The
emergency flag only means the text mentions something that may be life-threatening;
it is not a verified emergency, and the portal does not alert emergency services.

Algorithm (every step adds a human-readable factor):
  1. Start from the category's base level (CATEGORY_BASE; unknown categories -> medium).
  2. Critical hazard phrase (live wire, gas leak, open manhole, fire, collapse, trapped,
     flooding...) -> critical, and possible_emergency = True.
  3. Otherwise a health/safety-risk phrase (dog bite, sewage entering homes, contaminated
     water, fallen tree, accident...) raises the level to at least high.
  4. Vulnerable people (children, elderly, school, hospital), large scale (whole colony,
     many families) and strong urgency in the wording each raise the level by one step,
     but never above high: only step 2 can produce "critical".
  5. A long duration (a week or more) raises a low level to medium.
"""

import re
from dataclasses import dataclass, field

from app.ai.preprocessing import normalise
from app.ai.sentiment import analyse as analyse_sentiment

RULES_VERSION = "priority-rules-v1"
LEVELS = ["low", "medium", "high", "critical"]

CATEGORY_BASE: dict[str, int] = {
    "drainage-sewerage": 1, "garbage-sanitation": 1, "roads-potholes": 1, "street-lights": 1,
    "water-supply": 1, "electricity": 1, "stray-animals": 1, "public-health": 1,
    "encroachment": 0, "pollution": 0, "parks-trees": 0, "other": 0,
}
DEFAULT_BASE = 1

# Possible danger to life. Matching is on whole words of the normalised text.
CRITICAL_HAZARDS = [
    "live wire", "live electric wire", "still live", "hanging wire", "wire snapped", "wire fallen", "wire fell",
    "fallen wire", "electric shock", "got shock", "getting shocks", "electrocuted", "electrocution", "sparking",
    "gas leak", "gas leakage", "leaking gas", "cylinder blast", "open manhole", "manhole open",
    "manhole without cover", "lid is missing", "without any cover", "fire", "caught fire", "flames", "on fire",
    "collapse", "collapsed", "caved in", "sinkhole", "trapped", "stranded", "drowning", "drowned", "swept away",
    "flooding", "flooded", "unconscious", "bleeding", "hospitalised", "hospitalized", "someone will die",
    "without any barricade", "no barricading",
]
HIGH_RISKS = [
    "accident", "injured", "injury", "skidded", "fell", "dog bit", "bit a", "bit two", "bite", "bitten",
    "attacked", "attacking", "rabid", "foaming", "snake", "sewage entering", "entering our houses",
    "entering houses", "inside homes", "into homes", "came inside", "no water", "not come", "no drinking water",
    "contaminated", "smells of sewage", "smells like drainage", "muddy", "dengue", "malaria", "cholera",
    "diarrhoea", "vomiting", "fever cases", "tree fallen", "tree fell", "fallen tree", "uprooted",
    "may fall", "about to fall", "can fall", "leaning", "tilted", "bent", "no power", "power outage",
    "wires visible", "wires exposed", "exposed", "unsafe", "chain snatching", "breathing problem", "toxic",
    "chemical", "medical waste", "syringes", "biomedical", "health hazard", "health risk", "manhole cover",
    "manhole lid", "touching tree", "touch them",
]
VULNERABLE = [
    "child", "children", "kid", "kids", "boy", "girl", "school", "elderly", "senior citizen", "senior citizens",
    "old people", "old age", "pregnant", "hospital", "patients", "disabled", "handicapped",
]
SCALE = [
    "entire colony", "whole colony", "entire area", "whole area", "whole street", "entire street",
    "all the houses", "all houses", "families", "houses are affected", "hundreds", "whole road",
    "entire stretch", "many people", "several", "whole stretch",
]
LONG_DURATION_RE = re.compile(
    r"\b(?:week|weeks|month|months|year|years|long time)\b"
    r"|\b(?:since|from|for)\s+(?:the\s+)?(?:last\s+|past\s+)?(?:more than\s+)?([7-9]|[1-9]\d+)\s+days\b"
)
URGENCY_BUMP = 0.6

EMERGENCY_MESSAGE = (
    "Your description mentions something that may be dangerous to life ({keywords}). "
    "If anyone is in immediate danger, call 112 (national emergency number) now. "
    "Filing a complaint here does NOT alert emergency services."
)


@dataclass
class PriorityResult:
    level: str
    factors: list[str] = field(default_factory=list)
    possible_emergency: bool = False
    emergency_keywords: list[str] = field(default_factory=list)

    @property
    def emergency_message(self) -> str | None:
        if not self.possible_emergency:
            return None
        return EMERGENCY_MESSAGE.format(keywords=", ".join(f'"{k}"' for k in self.emergency_keywords))


def _matches(padded_text: str, phrases: list[str]) -> list[str]:
    return [p for p in phrases if f" {p} " in padded_text]


def detect_emergency(text: str) -> list[str]:
    """Life-threatening keywords found in the text (simple rules, no model)."""
    return _matches(f" {normalise(text)} ", CRITICAL_HAZARDS)


def _raise(level: int) -> int:
    return max(level, min(level + 1, 2))


def predict_priority(text: str, category_slug: str | None, category_name: str | None = None) -> PriorityResult:
    padded = f" {normalise(text)} "
    base = CATEGORY_BASE.get(category_slug or "", DEFAULT_BASE)
    level = base
    label = category_name or category_slug or "unknown category"
    factors = [f"Category baseline ({label}): {LEVELS[base]}"]

    hazards = _matches(padded, CRITICAL_HAZARDS)
    if hazards:
        level = 3
        factors.append(f"Possible danger to life mentioned: {', '.join(hazards[:3])}")
    else:
        risks = _matches(padded, HIGH_RISKS)
        if risks:
            level = max(level, 2)
            factors.append(f"Health or safety risk mentioned: {', '.join(risks[:3])}")

        vulnerable = _matches(padded, VULNERABLE)
        if vulnerable:
            level = _raise(level)
            factors.append(f"Vulnerable people affected: {', '.join(vulnerable[:3])}")

        scale = _matches(padded, SCALE)
        if scale:
            level = _raise(level)
            factors.append(f"Large number of people affected: {', '.join(scale[:2])}")

        urgency = analyse_sentiment(text).urgency
        if urgency >= URGENCY_BUMP:
            level = _raise(level)
            factors.append(f"Strongly urgent wording (urgency score {urgency:.2f})")

        if level == 0 and LONG_DURATION_RE.search(padded):
            level = 1
            factors.append("Problem has persisted for a week or more")

    return PriorityResult(
        level=LEVELS[level], factors=factors, possible_emergency=bool(hazards), emergency_keywords=hazards[:3]
    )
