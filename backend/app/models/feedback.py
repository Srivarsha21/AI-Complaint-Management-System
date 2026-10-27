"""Citizen feedback after a complaint is resolved (module 11)."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ComplaintFeedback(Base):
    __tablename__ = "complaint_feedback"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # One feedback per complaint, from its complainant.
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_satisfactorily: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Whether the AI suggestions shown while filing were useful; None = not answered.
    ai_helpful: Mapped[bool | None] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
