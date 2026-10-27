"""Unit tests for the module 5 AI components (no database or web layer involved)."""

import pytest
from sklearn.metrics import f1_score

from app.ai import classifier, sentiment
from app.ai.duplicates import Candidate, find_duplicates, haversine_m
from app.ai.preprocessing import clean_text, complaint_text, normalise, redact
from app.ai.priority import detect_emergency, predict_priority
from app.ai.train import load_dataset, split_dataset

# --- Preprocessing ---------------------------------------------------------------------------

def test_redact_removes_urls_emails_and_phone_numbers():
    text = "Call me on +91 98765 43210 or 9876543210, mail ravi.k@example.com, see https://x.in/a?b=1 www.y.com"
    cleaned = redact(text)
    for secret in ("98765", "9876543210", "ravi.k@example.com", "https://", "www.y.com"):
        assert secret not in cleaned


def test_normalise_lowercases_strips_punctuation_and_expands_shorthand():
    assert normalise("  Pls FIX the   drain!!! ASAP...") == "please fix the drain immediately"


def test_clean_text_drops_stopwords_but_keeps_negations():
    assert clean_text("The street light is NOT working since 3 days, sir") == "street light not working since 3 days"


def test_complaint_text_joins_subject_and_description():
    assert complaint_text("Drain blocked", "Water overflowing") == "Drain blocked. Water overflowing"
    assert complaint_text("", "Only description") == "Only description"


# --- Category classifier -----------------------------------------------------------------------

def test_classifier_regression_guard_on_synthetic_test_split():
    """REGRESSION GUARD ON SYNTHETIC DATA, not a real-world accuracy claim.

    Re-creates train.py's fixed held-out split and checks the committed model still
    scores well on it. Synthetic template data is easy, so a high bar is expected here;
    failing it means the artifact, preprocessing or dataset changed unexpectedly.
    """
    classifier.reset_cache()
    bundle = classifier.load_bundle()
    assert bundle is not None, "model artifact missing; run `python -m app.ai.train`"
    _, test = split_dataset(load_dataset())
    predicted = bundle["pipeline"].predict(test["text"])
    assert f1_score(test["category_slug"], predicted, average="macro") >= 0.90


def test_classifier_predicts_ranked_probabilities():
    result = classifier.predict("Transformer sparking near our colony, current keeps going")
    assert result is not None
    assert result.slug == "electricity"
    assert result.ranked[0][1] >= result.ranked[1][1]
    assert sum(p for _, p in result.ranked) == pytest.approx(1.0, abs=1e-6)
    assert result.model_version.startswith("tfidf-logreg-")


def test_classifier_returns_none_when_model_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "model_path", lambda: tmp_path / "missing.joblib")
    classifier.reset_cache()
    try:
        assert classifier.predict("Garbage not collected") is None
        assert classifier.is_available() is False
    finally:
        monkeypatch.undo()
        classifier.reset_cache()


# --- Priority rules -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, keyword",
    [
        ("A live wire is hanging over the road", "live wire"),
        ("Strong gas leak smell from the pipeline", "gas leak"),
        ("Open manhole in front of the school gate", "open manhole"),
        ("The old wall collapsed on the footpath", "collapsed"),
    ],
)
def test_emergency_keywords_make_priority_critical(text, keyword):
    result = predict_priority(text, "other")
    assert result.level == "critical"
    assert result.possible_emergency is True
    assert keyword in result.emergency_keywords
    assert "112" in result.emergency_message
    assert keyword in detect_emergency(text)


def test_emergency_keywords_match_whole_words_only():
    # "firecrackers" must not trigger "fire".
    result = predict_priority("Firecrackers burst till 2 am every weekend", "pollution")
    assert result.possible_emergency is False
    assert result.emergency_message is None


def test_priority_factors_explain_each_step():
    result = predict_priority(
        "Stray dog bit a child near the school. The entire colony is scared.", "stray-animals", "Stray Animals"
    )
    assert result.level == "high"
    joined = " | ".join(result.factors)
    assert "Category baseline (Stray Animals): medium" in joined
    assert "Health or safety risk" in joined
    assert "Vulnerable people" in joined
    assert "Large number of people" in joined
    assert result.possible_emergency is False


def test_priority_low_request_and_long_duration_bump():
    assert predict_priority("Please trim the tree branches", "parks-trees").level == "low"
    long = predict_priority("Tree branches need trimming, pending for 2 months", "parks-trees")
    assert long.level == "medium"
    assert "week or more" in long.factors[-1]


def test_unknown_category_uses_default_medium_base():
    assert predict_priority("Something is wrong here", None).level == "medium"


# --- Sentiment ----------------------------------------------------------------------------

def test_sentiment_labels():
    assert sentiment.analyse("Very bad smell, terrible and dirty, people suffering").label == "negative"
    assert sentiment.analyse("Thank you, the problem was fixed quickly. Good work").label == "positive"
    assert sentiment.analyse("The light is at the corner of the road").label == "neutral"


def test_sentiment_negation_flips_polarity():
    assert sentiment.analyse("The work is good").score > 0
    assert sentiment.analyse("The work is not good").score < 0


def test_urgency_score_rises_with_urgent_wording():
    calm = sentiment.analyse("The park bench is broken").urgency
    urgent = sentiment.analyse("URGENT!!! Danger, please help immediately").urgency
    assert calm == 0
    assert urgent >= 0.6
    assert 0 <= urgent <= 1


# --- Duplicates (pure functions) ----------------------------------------------------------------

def test_haversine_known_distance():
    # One degree of latitude is about 111.2 km.
    assert haversine_m(17.0, 78.0, 18.0, 78.0) == pytest.approx(111_195, rel=0.001)
    assert haversine_m(17.4, 78.4, 17.4, 78.4) == 0


def test_find_duplicates_threshold_ranking_and_geo():
    query = "Garbage not collected for a week near the bus stop in Ameerpet"
    candidates = [
        Candidate(1, "Garbage not collected near the bus stop in Ameerpet for days", 17.4375, 78.4483),
        Candidate(2, "Street light not working in Kondapur", 17.4375, 78.4483),
        Candidate(3, "Garbage not collected near the bus stop in Ameerpet", 17.5375, 78.4483),  # ~11 km away
        Candidate(4, "Garbage has not been collected near the Ameerpet bus stop"),  # no coordinates
    ]
    matches = find_duplicates(query, candidates, latitude=17.4376, longitude=78.4484, threshold=0.3)
    ids = [m.candidate.id for m in matches]
    assert 1 in ids and 4 in ids
    assert 2 not in ids  # dissimilar text
    assert 3 not in ids  # same text but too far away
    near = next(m for m in matches if m.candidate.id == 1)
    assert near.distance_m is not None and near.distance_m < 50
    assert near.similarity > near.text_similarity  # proximity boost
    assert next(m for m in matches if m.candidate.id == 4).distance_m is None
    assert matches == sorted(matches, key=lambda m: m.similarity, reverse=True)


def test_find_duplicates_handles_empty_input():
    assert find_duplicates("anything", []) == []
    assert find_duplicates("!!!", [Candidate(1, "garbage")]) == []
