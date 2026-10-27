"""Cached image-analysis results for complaint attachments."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttachmentAnalysis(Base):
    __tablename__ = "attachment_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("complaint_attachments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # The ImageAnalysisOut payload as returned by the API.
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Results computed with another model/threshold are recomputed on the next request.
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
