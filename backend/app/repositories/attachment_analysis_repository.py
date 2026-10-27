"""Database access for cached attachment analyses."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment_analysis import AttachmentAnalysis


def get_for_attachment(db: Session, attachment_id: int) -> AttachmentAnalysis | None:
    return db.scalar(select(AttachmentAnalysis).where(AttachmentAnalysis.attachment_id == attachment_id))


def save(db: Session, *, attachment_id: int, result: dict, model_version: str) -> AttachmentAnalysis:
    """Insert or replace the cached analysis for an attachment (caller commits)."""
    row = get_for_attachment(db, attachment_id)
    if row is None:
        row = AttachmentAnalysis(attachment_id=attachment_id, result=result, model_version=model_version)
        db.add(row)
    else:
        row.result = result
        row.model_version = model_version
    db.flush()
    return row
