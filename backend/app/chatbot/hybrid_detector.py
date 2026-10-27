"""Chatbot category detection: keyword rules first, ML classifier as fallback.

Keyword rules handle Telugu/Hinglish words and explain what matched, so they
win whenever they find a category. When they find nothing, the module-5
TF-IDF classifier is consulted, but only a confident prediction is used;
otherwise the bot keeps asking the user to describe the problem.
"""

from app.ai import classifier
from app.chatbot.categories import CategoryDetection, KeywordCategoryDetector

ML_MIN_CONFIDENCE = 0.5


class HybridCategoryDetector:
    def __init__(self, min_confidence: float = ML_MIN_CONFIDENCE) -> None:
        self._keywords = KeywordCategoryDetector()
        self._min_confidence = min_confidence

    def detect(self, text: str) -> CategoryDetection:
        keyword_result = self._keywords.detect(text)
        if keyword_result.slug is not None:
            return keyword_result
        try:
            prediction = classifier.predict(text)
        except Exception:  # noqa: BLE001 - the classifier is optional for the chatbot
            prediction = None
        if prediction is None or prediction.confidence < self._min_confidence:
            return keyword_result
        alternatives = tuple(slug for slug, _ in prediction.ranked[1:3])
        return CategoryDetection(prediction.slug, prediction.confidence, ("ml-classifier",), alternatives)
