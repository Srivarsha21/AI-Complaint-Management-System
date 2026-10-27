"""Complaint category detection behind a small, swappable interface.

The default `KeywordCategoryDetector` scores weighted keyword rules per
category (English plus common Hinglish and Telugu words, in Latin script and
in Telugu/Devanagari script). Another detector (e.g. the ML text classifier)
can be plugged in with `set_detector()` as long as it implements
`CategoryDetector.detect`.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CategoryDetection:
    slug: str | None
    confidence: float  # 0..1, comparable only within one detector
    matched: tuple[str, ...] = ()
    # Other plausible categories when the text is ambiguous.
    alternatives: tuple[str, ...] = field(default_factory=tuple)


class CategoryDetector(Protocol):
    def detect(self, text: str) -> CategoryDetection: ...


# slug -> list of (keyword, weight). Multi-word phrases weigh more, so that
# "street light" beats the generic "light", "drinking water" beats "water".
# Latin-script keywords match whole words (with an optional plural "s"/"es");
# keywords in other scripts match as substrings.
KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "drainage-sewerage": [
        ("drain", 2), ("drainage", 2), ("sewer", 2), ("sewage", 2), ("sewerage", 2), ("manhole", 2),
        ("gutter", 2), ("nala", 2), ("nalla", 1), ("nallah", 2), ("naala", 2), ("naali", 2), ("nali", 1),
        ("waterlogging", 2), ("water logging", 3), ("water logged", 3), ("overflowing drain", 3),
        ("drain overflow", 3), ("blocked drain", 3), ("drainage block", 3), ("sewage overflow", 3),
        ("open manhole", 3), ("muriki kaluva", 3), ("kaluva", 1), ("mori", 1), ("dirty water on road", 3),
        ("డ్రైనేజ", 2), ("మురుగు", 2), ("మ్యాన్‌హోల్", 2), ("नाली", 2), ("सीवर", 2), ("गटर", 2),
    ],
    "garbage-sanitation": [
        ("garbage", 2), ("trash", 2), ("rubbish", 2), ("waste", 1), ("dustbin", 2), ("bin", 1),
        ("litter", 2), ("dump", 1), ("dumping", 2), ("kachra", 2), ("kachara", 2), ("kooda", 2),
        ("kuda", 1), ("chetta", 2), ("sweeping", 2), ("sweeper", 2), ("sanitation", 2), ("safai", 2),
        ("public toilet", 3), ("toilet", 1), ("dirty street", 3), ("garbage collection", 3),
        ("garbage not collected", 3), ("swachh", 1), ("చెత్త", 2), ("कचरा", 2), ("कूड़ा", 2),
    ],
    "roads-potholes": [
        ("pothole", 3), ("road", 1), ("roads", 1), ("footpath", 1), ("speed breaker", 3), ("speedbreaker", 3),
        ("road damage", 3), ("damaged road", 3), ("broken road", 3), ("road repair", 3), ("gaddha", 2),
        ("gadda", 2), ("khadda", 2), ("sadak", 2), ("rasta", 1), ("roddu", 2), ("rodu", 1), ("gunta", 2),
        ("గుంత", 2), ("రోడ్డు", 2), ("गड्ढा", 2), ("सड़क", 2),
    ],
    "street-lights": [
        ("street light", 4), ("streetlight", 4), ("street lamp", 4), ("lamp post", 3), ("lamppost", 3),
        ("light pole", 2), ("street lights", 4), ("lights not working", 2), ("light not working", 2),
        ("batti", 1), ("veedhi deepam", 3), ("veedhi light", 3), ("వీధి దీపం", 3), ("స్ట్రీట్ లైట్", 4),
        ("स्ट्रीट लाइट", 4),
    ],
    "water-supply": [
        ("water supply", 3), ("no water", 3), ("drinking water", 3), ("tap", 1), ("tap water", 3),
        ("pipeline", 2), ("pipe leak", 3), ("water leak", 3), ("leakage", 1), ("low pressure", 2),
        ("contaminated water", 3), ("dirty water supply", 3), ("water tanker", 3), ("tanker", 1),
        ("paani", 2), ("pani", 1), ("neellu", 2), ("neeru", 2), ("manchi neellu", 3), ("nalla neellu", 3),
        ("water connection", 2), ("water bill", 2), ("నీళ్ళు", 2), ("నీరు", 2), ("పానీ", 1), ("पानी", 2),
    ],
    "electricity": [
        ("power cut", 3), ("powercut", 3), ("power outage", 3), ("no power", 3), ("electricity", 2),
        ("electric", 1), ("current", 1), ("current poyindi", 3), ("current ledu", 3), ("karent", 2),
        ("transformer", 2), ("voltage", 2), ("low voltage", 3), ("live wire", 3), ("hanging wire", 3),
        ("electric pole", 3), ("electric shock", 3), ("meter", 1), ("bijli", 2), ("light gayi", 2),
        ("vidyut", 2), ("కరెంట్", 2), ("విద్యుత్", 2), ("बिजली", 2),
    ],
    "stray-animals": [
        ("stray", 2), ("stray dog", 3), ("dog", 1), ("dogs", 1), ("dog bite", 3), ("cattle", 2),
        ("cow", 1), ("buffalo", 1), ("monkey", 2), ("pig", 1), ("dead animal", 3), ("animal", 1),
        ("kutta", 2), ("kutte", 2), ("kukka", 2), ("kukkalu", 2), ("aavu", 1), ("kothi", 2), ("bandar", 2),
        ("కుక్క", 2), ("కోతి", 2), ("कुत्ता", 2), ("कुत्ते", 2),
    ],
    "encroachment": [
        ("encroach", 3), ("encroachment", 3), ("encroached", 3), ("illegal construction", 3),
        ("unauthorised construction", 3), ("unauthorized construction", 3), ("illegal building", 3),
        ("footpath occupied", 3), ("occupied footpath", 3), ("kabza", 2), ("kabja", 2),
        ("lake encroachment", 4), ("govt land", 2), ("government land", 2), ("aakramana", 2),
        ("ఆక్రమణ", 2), ("अतिक्रमण", 2), ("कब्जा", 2),
    ],
    "public-health": [
        ("mosquito", 3), ("mosquitoes", 3), ("dengue", 3), ("malaria", 3), ("fogging", 3),
        ("stagnant water", 3), ("breeding", 2), ("machhar", 2), ("macchar", 2), ("machar", 2),
        ("domalu", 2), ("doma", 1), ("anti larval", 3), ("దోమ", 2), ("मच्छर", 2),
    ],
    "pollution": [
        ("pollution", 2), ("noise", 2), ("loudspeaker", 3), ("loud speaker", 3), ("dj", 1), ("smoke", 2),
        ("air pollution", 3), ("noise pollution", 3), ("burning", 1), ("burning garbage", 3),
        ("garbage burning", 3), ("dust", 1), ("factory smoke", 3), ("effluent", 3), ("industrial waste", 3),
        ("shor", 2), ("dhuan", 2), ("dhuvan", 2), ("kalushyam", 2), ("sound", 1),
        ("కాలుష్యం", 2), ("శబ్దం", 2), ("प्रदूषण", 2), ("धुआं", 2), ("शोर", 2),
    ],
    "parks-trees": [
        ("tree", 2), ("trees", 2), ("fallen tree", 3), ("tree fallen", 3), ("tree trimming", 3),
        ("branch", 2), ("branches", 2), ("park", 2), ("garden", 1), ("playground", 1), ("ped", 1),
        ("chettu", 2), ("chetlu", 2), ("kommalu", 2), ("చెట్టు", 2), ("పార్క్", 2), ("पेड़", 2),
    ],
}

_SCRIPT_LATIN = re.compile(r"^[\x00-\x7f]+$")


def _compile(keyword: str) -> re.Pattern[str]:
    if _SCRIPT_LATIN.match(keyword):
        words = r"\s+".join(re.escape(w) for w in keyword.split())
        return re.compile(rf"(?<![a-z0-9]){words}(?:e?s)?(?![a-z0-9])")
    return re.compile(re.escape(keyword))


_RULES: dict[str, list[tuple[str, float, re.Pattern[str]]]] = {
    slug: [(kw, weight, _compile(kw.lower())) for kw, weight in rules] for slug, rules in KEYWORDS.items()
}


class KeywordCategoryDetector:
    """Rule-based detector; deterministic and explainable (returns matched words)."""

    def __init__(self, min_score: float = 1.0) -> None:
        self.min_score = min_score

    def detect(self, text: str) -> CategoryDetection:
        lowered = " ".join((text or "").lower().split())
        if not lowered:
            return CategoryDetection(None, 0.0)

        scores: dict[str, float] = {}
        matches: dict[str, list[str]] = {}
        for slug, rules in _RULES.items():
            for keyword, weight, pattern in rules:
                if pattern.search(lowered):
                    scores[slug] = scores.get(slug, 0.0) + weight
                    matches.setdefault(slug, []).append(keyword)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or ranked[0][1] < self.min_score:
            return CategoryDetection(None, 0.0)

        best_slug, best = ranked[0]
        runners_up = tuple(slug for slug, score in ranked[1:] if score == best)
        total = sum(scores.values())
        if runners_up:
            # A tie is genuinely ambiguous: let the conversation ask the user.
            return CategoryDetection(None, best / total, alternatives=(best_slug, *runners_up))
        return CategoryDetection(best_slug, best / total, tuple(matches[best_slug]))


_detector: CategoryDetector = KeywordCategoryDetector()


def get_detector() -> CategoryDetector:
    return _detector


def set_detector(detector: CategoryDetector) -> None:
    """Swap in another detector, e.g. the trained text classifier."""
    global _detector
    _detector = detector


def detect_category(text: str) -> CategoryDetection:
    return _detector.detect(text)
