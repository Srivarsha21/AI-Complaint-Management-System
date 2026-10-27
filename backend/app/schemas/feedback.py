"""Feedback and AI-review schemas (module 11)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint import ComplaintPriority, ComplaintStatus, PrioritySource
from app.schemas.complaint import CategoryBrief


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    resolved_satisfactorily: bool
    ai_helpful: bool | None = None
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: int
    rating: int
    resolved_satisfactorily: bool
    ai_helpful: bool | None
    comment: str | None
    created_at: datetime


ReviewStatus = Literal["unreviewed", "correct", "incorrect"]
Signal = Literal["category_changed", "suggestion_rejected", "priority_overridden", "ai_not_helpful"]


class ReviewComplaint(BaseModel):
    id: int
    reference_number: str
    subject: str
    status: ComplaintStatus


class AIReviewItem(BaseModel):
    prediction_id: int
    complaint: ReviewComplaint
    final_category: CategoryBrief
    predicted_category: CategoryBrief | None
    category_confidence: float | None
    user_accepted_category: bool | None
    predicted_priority: ComplaintPriority | None
    final_priority: ComplaintPriority | None
    priority_source: PrioritySource | None
    signals: list[Signal]
    review_status: ReviewStatus
    corrected_category: CategoryBrief | None
    review_note: str | None
    reviewed_at: datetime | None
    model_version: str | None


class AIReviewPage(BaseModel):
    items: list[AIReviewItem]
    total: int


class AIReviewUpdate(BaseModel):
    review_status: Literal["correct", "incorrect"]
    corrected_category_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=1000)


class QualitySummary(BaseModel):
    """Computed from stored records. Agreement is with the category finally chosen
    by the citizen; it is a usage signal, not a measured accuracy."""

    predictions: int
    with_category_suggestion: int
    category_agreement_rate: float | None
    suggestion_acceptance_rate: float | None
    priority_overrides: int
    reviewed: int
    marked_incorrect: int
    feedback_count: int
    average_rating: float | None
    satisfied_rate: float | None
    ai_helpful_rate: float | None
