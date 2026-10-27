"""Request/response schemas for the AI endpoints.

- Text analysis, stored predictions and priority override (module 5).
- Image analysis and translation (modules 9-10).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.complaint import ComplaintPriority, ComplaintStatus, PrioritySource
from app.schemas.complaint import DepartmentBrief

DISCLAIMER = (
    "These are automatic suggestions from a model trained on a synthetic (machine-generated) dataset and "
    "simple rules. They can be wrong: you choose the category, and staff review the priority. "
    "This portal is not an emergency service - if anyone is in danger, call 112."
)


# --- Text analysis (module 5) ------------------------------------------------------

class AnalyzeRequest(BaseModel):
    subject: str = Field(default="", max_length=150)
    description: str = Field(min_length=10, max_length=5000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    # The category the user already picked, if any: used for the priority baseline and duplicate search.
    category_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check(self) -> "AnalyzeRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        return self


class CategorySuggestion(BaseModel):
    id: int
    name: str
    slug: str
    confidence: float


class PriorityOut(BaseModel):
    level: ComplaintPriority
    factors: list[str]


class SentimentOut(BaseModel):
    label: Literal["negative", "neutral", "positive"]
    score: float
    urgency: float


class DuplicateOut(BaseModel):
    """A possible duplicate. For non-staff callers only reference, status and similarity are filled."""

    reference_number: str | None
    status: ComplaintStatus
    similarity: float
    complaint_id: int | None = None
    subject: str | None = None
    distance_m: float | None = None


class AnalyzeResponse(BaseModel):
    model_status: Literal["ready", "not_trained"]
    category: CategorySuggestion | None
    alternatives: list[CategorySuggestion]
    department: DepartmentBrief | None
    priority: PriorityOut
    sentiment: SentimentOut
    possible_emergency: bool
    emergency_message: str | None
    duplicates: list[DuplicateOut]
    model_version: str | None
    disclaimer: str = DISCLAIMER


class StoredPredictionOut(BaseModel):
    predicted_category: CategorySuggestion | None
    predicted_priority: ComplaintPriority | None
    priority_factors: list[str]
    sentiment_label: str | None
    sentiment_score: float | None
    urgency_score: float | None
    possible_emergency: bool
    duplicate_candidates: list[dict[str, Any]]
    model_version: str | None
    user_accepted_category: bool | None
    created_at: datetime


class ComplaintAIOut(BaseModel):
    complaint_id: int
    prediction: StoredPredictionOut | None
    priority: ComplaintPriority | None
    priority_source: PrioritySource | None
    similar: list[DuplicateOut]
    model_status: Literal["ready", "not_trained"]
    disclaimer: str = DISCLAIMER


class PriorityOverride(BaseModel):
    priority: ComplaintPriority
    note: str | None = Field(default=None, max_length=500)


# --- Image analysis and translation (modules 9-10) ----------------------------------

class DetectionOut(BaseModel):
    label: str
    confidence: float
    box: list[float] = Field(description="[x1, y1, x2, y2] in original image pixels")


class CategoryHintOut(BaseModel):
    slug: str
    reason: str


class ImageAnalysisOut(BaseModel):
    valid: bool
    width: int
    height: int
    blur_score: float
    is_blurry: bool
    brightness: float
    too_dark: bool
    too_bright: bool
    detections: list[DetectionOut]
    category_hints: list[CategoryHintOut]
    detector_available: bool
    model: str
    disclaimer: str


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source: Literal["te", "en", "auto"] = "auto"
    target: Literal["en", "te"] = "en"

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text to translate is empty")
        return value


class TranslateOut(BaseModel):
    translated_text: str
    source_language: Literal["te", "en"]
    target_language: Literal["te", "en"]
    provider: Literal["gemini"] = "gemini"
