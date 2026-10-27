"""Category classifier: TF-IDF (word 1-2 grams + character 2-5 grams) + logistic regression.

The trained pipeline is saved by `python -m app.ai.train` to
app/ai/artifacts/category_model.joblib. It is loaded lazily on first use and
cached. If the file is missing or unreadable, `predict()` returns None and
callers fall back to "model not trained" instead of failing.
"""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.ai.preprocessing import clean_text
from app.core.config import BACKEND_DIR, get_settings

logger = logging.getLogger(__name__)

MODEL_FILENAME = "category_model.joblib"


def build_pipeline(seed: int = 42) -> Pipeline:
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(preprocessor=clean_text, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            (
                "char",
                TfidfVectorizer(
                    preprocessor=clean_text, analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True,
                    max_features=40000,
                ),
            ),
        ]
    )
    model = LogisticRegression(C=5.0, max_iter=3000, class_weight="balanced", random_state=seed)
    return Pipeline([("features", features), ("model", model)])


def artifacts_dir() -> Path:
    path = Path(get_settings().ai_artifacts_dir)
    return path if path.is_absolute() else BACKEND_DIR / path


def model_path() -> Path:
    return artifacts_dir() / MODEL_FILENAME


@dataclass(frozen=True)
class CategoryPrediction:
    ranked: list[tuple[str, float]]  # (slug, probability), best first
    model_version: str

    @property
    def slug(self) -> str:
        return self.ranked[0][0]

    @property
    def confidence(self) -> float:
        return self.ranked[0][1]


_lock = threading.Lock()
_cache: dict[str, Any] = {}


def load_bundle() -> dict[str, Any] | None:
    """The saved {pipeline, version, ...} bundle, or None when not trained / unreadable."""
    with _lock:
        if "bundle" not in _cache:
            path = model_path()
            bundle = None
            if path.is_file():
                try:
                    bundle = joblib.load(path)
                except Exception:  # corrupt file or incompatible library version
                    logger.exception("could not load category model from %s", path)
            else:
                logger.warning("category model not found at %s; run `python -m app.ai.train`", path)
            _cache["bundle"] = bundle
        return _cache["bundle"]


def reset_cache() -> None:
    with _lock:
        _cache.clear()


def is_available() -> bool:
    return load_bundle() is not None


def predict(text: str) -> CategoryPrediction | None:
    bundle = load_bundle()
    if bundle is None or not clean_text(text):
        return None
    pipeline: Pipeline = bundle["pipeline"]
    probabilities = pipeline.predict_proba([text])[0]
    ranked = sorted(
        ((str(label), float(p)) for label, p in zip(pipeline.classes_, probabilities)),
        key=lambda item: item[1],
        reverse=True,
    )
    return CategoryPrediction(ranked=ranked, model_version=bundle["version"])
