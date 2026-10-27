"""Possible-duplicate detection: TF-IDF cosine similarity plus geographic proximity.

Pure functions; the database query for candidates lives in
app/repositories/ai_repository.py. A match never blocks a submission: it is
only shown so the citizen or staff can decide.

Scoring for each candidate (same category, not closed, inside the time window):
  * text_similarity = cosine similarity of word 1-2 gram TF-IDF vectors
    (the vectoriser is fitted on the new complaint plus its candidates).
  * If BOTH complaints have coordinates:
        distance > max_distance_m        -> not a duplicate (different place)
        otherwise score = similarity + geo_boost * (1 - distance / max_distance_m)
  * Otherwise score = text_similarity (location unknown, no boost).
  * Matches with score >= threshold are returned, best first, capped at score 1.0.
"""

import math
from dataclasses import dataclass
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ai.preprocessing import clean_text

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Candidate:
    id: int
    text: str
    latitude: float | None = None
    longitude: float | None = None
    payload: Any = None  # e.g. the ORM object, passed through untouched


@dataclass(frozen=True)
class DuplicateMatch:
    candidate: Candidate
    similarity: float  # final score 0..1
    text_similarity: float
    distance_m: float | None


def find_duplicates(
    text: str,
    candidates: list[Candidate],
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    threshold: float = 0.35,
    max_distance_m: float = 500.0,
    geo_boost: float = 0.15,
    limit: int = 5,
) -> list[DuplicateMatch]:
    if not candidates or not clean_text(text):
        return []
    docs = [clean_text(text)] + [clean_text(c.text) for c in candidates]
    vectoriser = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    try:
        matrix = vectoriser.fit_transform(docs)
    except ValueError:  # empty vocabulary
        return []
    sims = cosine_similarity(matrix[0], matrix[1:]).ravel()

    matches: list[DuplicateMatch] = []
    for candidate, sim in zip(candidates, sims):
        text_sim = float(sim)
        distance = None
        score = text_sim
        if None not in (latitude, longitude, candidate.latitude, candidate.longitude):
            distance = haversine_m(latitude, longitude, candidate.latitude, candidate.longitude)  # type: ignore[arg-type]
            if distance > max_distance_m:
                continue
            score = text_sim + geo_boost * (1 - distance / max_distance_m)
        if score >= threshold:
            matches.append(
                DuplicateMatch(
                    candidate=candidate,
                    similarity=round(min(1.0, score), 3),
                    text_similarity=round(text_sim, 3),
                    distance_m=round(distance, 1) if distance is not None else None,
                )
            )
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:limit]
