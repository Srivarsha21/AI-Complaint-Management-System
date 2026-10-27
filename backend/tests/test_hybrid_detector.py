"""Chatbot category detection: keywords first, ML classifier fallback (modules 5 + 8)."""

from app.ai import classifier
from app.ai.classifier import CategoryPrediction
from app.chatbot.hybrid_detector import HybridCategoryDetector


def test_keyword_match_wins_over_classifier(monkeypatch):
    monkeypatch.setattr(classifier, "predict", lambda text: CategoryPrediction([("electricity", 0.99)], "test"))
    result = HybridCategoryDetector().detect("There is a blocked drain in my street")
    assert result.slug == "drainage-sewerage"


def test_confident_classifier_used_when_no_keyword(monkeypatch):
    monkeypatch.setattr(
        classifier, "predict",
        lambda text: CategoryPrediction([("roads-potholes", 0.81), ("other", 0.1), ("electricity", 0.05)], "test"),
    )
    result = HybridCategoryDetector().detect("bikes keep slipping near the junction crater")
    assert result.slug == "roads-potholes"
    assert result.alternatives == ("other", "electricity")


def test_unsure_classifier_is_ignored(monkeypatch):
    monkeypatch.setattr(classifier, "predict", lambda text: CategoryPrediction([("other", 0.3)], "test"))
    assert HybridCategoryDetector().detect("hello there").slug is None


def test_classifier_failure_falls_back_to_keywords(monkeypatch):
    def boom(text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(classifier, "predict", boom)
    assert HybridCategoryDetector().detect("hello there").slug is None
