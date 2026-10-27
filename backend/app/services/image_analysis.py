"""Image analysis for complaint photos: OpenCV quality checks + YOLOv8n detections.

Results are advisory. Category hints are derived conservatively from COCO
object classes and are never applied automatically.
"""

import logging

import numpy as np
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.vision import detector as detector_module
from app.ai.vision.detector import MODEL_LABEL, Detection, DetectorUnavailable
from app.ai.vision.quality import assess_quality, decode_image
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.models.user import User
from app.repositories import attachment_analysis_repository
from app.schemas.ai import CategoryHintOut, DetectionOut, ImageAnalysisOut
from app.services import complaint_service, file_storage

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Automated analysis using a general-purpose YOLOv8n model trained on 80 everyday object classes (COCO: people, "
    "vehicles, animals, etc.). It cannot recognise potholes, garbage, drainage overflow, broken street lights or other "
    "civic problems. Detections and hints are for reference only and may be wrong; they never change your complaint."
)

# COCO label -> (category slug, reason). Deliberately small and conservative.
_ANIMALS = {"dog", "cat", "cow", "horse", "sheep"}
_VEHICLES = {"car", "truck", "bus", "motorcycle", "bicycle"}
_ROAD_OBJECTS = {"traffic light", "stop sign"}


def _category_hints(detections: list[Detection]) -> list[CategoryHintOut]:
    labels = {d.label for d in detections}
    hints: list[CategoryHintOut] = []
    animals = sorted(labels & _ANIMALS)
    if animals:
        hints.append(CategoryHintOut(
            slug="stray-animals",
            reason=f"Animal detected ({', '.join(animals)}). If the complaint is about stray animals, "
                   "'Stray Animals' may fit.",
        ))
    road = sorted(labels & (_VEHICLES | _ROAD_OBJECTS))
    if road:
        hints.append(CategoryHintOut(
            slug="roads-potholes",
            reason=f"Road or traffic context ({', '.join(road)}). The model cannot see road damage itself; "
                   "choose 'Roads & Potholes' only if the problem is with the road.",
        ))
    if "fire hydrant" in labels:
        hints.append(CategoryHintOut(
            slug="water-supply",
            reason="Fire hydrant detected: possible water-supply context.",
        ))
    return hints


def model_version() -> str:
    settings = get_settings()
    return f"{MODEL_LABEL}|{settings.vision_model_file}|conf={settings.vision_confidence_threshold}"


def analyse_image(image: np.ndarray) -> ImageAnalysisOut:
    settings = get_settings()
    report = assess_quality(
        image,
        blur_threshold=settings.vision_blur_threshold,
        dark_threshold=settings.vision_dark_threshold,
        bright_threshold=settings.vision_bright_threshold,
    )
    try:
        detections = detector_module.get_detector().detect(image)
        available = True
    except DetectorUnavailable as exc:
        logger.info("image analysis without detector: %s", exc)
        detections, available = [], False

    return ImageAnalysisOut(
        valid=True,
        width=report.width,
        height=report.height,
        blur_score=report.blur_score,
        is_blurry=report.is_blurry,
        brightness=report.brightness,
        too_dark=report.too_dark,
        too_bright=report.too_bright,
        detections=[DetectionOut(label=d.label, confidence=d.confidence, box=list(d.box)) for d in detections],
        category_hints=_category_hints(detections),
        detector_available=available,
        model=MODEL_LABEL,
        disclaimer=DISCLAIMER,
    )


def analyse_upload(upload: UploadFile) -> ImageAnalysisOut:
    """Validate (same limits as complaint uploads) and analyse. Nothing is stored."""
    validated = file_storage.read_validated_image(upload)
    return analyse_image(validated.image)


def analyse_attachment(db: Session, *, user: User, complaint_id: int, attachment_id: int) -> ImageAnalysisOut:
    attachment = complaint_service.get_attachment_for_user(
        db, user=user, complaint_id=complaint_id, attachment_id=attachment_id
    )
    version = model_version()
    cached = attachment_analysis_repository.get_for_attachment(db, attachment.id)
    if cached is not None and cached.model_version == version:
        return ImageAnalysisOut.model_validate(cached.result)

    path = file_storage.path_for(attachment.stored_filename)
    if not path.is_file():
        raise NotFoundError("Attachment file is missing.")
    image = decode_image(path.read_bytes())
    if image is None:
        raise NotFoundError("Attachment could not be read as an image.")

    result = analyse_image(image)
    # Only complete results are cached; an OpenCV-only result is retried next time.
    if result.detector_available:
        try:
            attachment_analysis_repository.save(
                db, attachment_id=attachment.id, result=result.model_dump(mode="json"), model_version=version
            )
            db.commit()
        except IntegrityError:
            db.rollback()  # a concurrent request cached it first; its result is equivalent
    return result
