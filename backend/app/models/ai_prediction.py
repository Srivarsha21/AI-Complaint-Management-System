"""AI analysis stored for each complaint at submission time (module 5).

Everything here is a PREDICTION for staff triage. `complaints.priority` is
copied from `predicted_priority` with `priority_source = 'ai'` until a staff
member overrides it.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.complaint import ComplaintPriority, _enum
from app.models.department import Category


class ComplaintAIPrediction(Base):
    __tablename__ = "complaint_ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    # None when the classifier is not trained or no category with that slug exists.
    predicted_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category_confidence: Mapped[float | None] = mapped_column(Float)
    predicted_priority: Mapped[ComplaintPriority | None] = mapped_column(_enum(ComplaintPriority))
    priority_factors: Mapped[list[str] | None] = mapped_column(JSON)
    sentiment_label: Mapped[str | None] = mapped_column(String(10))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    urgency_score: Mapped[float | None] = mapped_column(Float)
    possible_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # [{complaint_id, reference_number, status, similarity, distance_m}] at submission time.
    duplicate_candidates: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(64))
    # True: the citizen kept the AI-suggested category; False: chose another; None: no suggestion was shown.
    user_accepted_category: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Human review (module 11). Reviews never retrain the model automatically;
    # reviewed corrections can be exported and used in a deliberate, manual retraining.
    review_status: Mapped[str] = mapped_column(String(20), default="unreviewed", server_default="unreviewed", nullable=False)
    corrected_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    predicted_category: Mapped[Category | None] = relationship(lazy="joined", foreign_keys=[predicted_category_id])
    corrected_category: Mapped[Category | None] = relationship(lazy="joined", foreign_keys=[corrected_category_id])
