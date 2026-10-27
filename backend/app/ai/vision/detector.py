"""YOLOv8n object detector (pre-trained on the 80 COCO classes).

IMPORTANT: this off-the-shelf model recognises everyday objects such as
people, vehicles, animals, traffic lights and fire hydrants. It was NOT trained
on civic problems and cannot detect potholes, garbage, drainage overflow,
broken street lights or similar. Its output is context for a human reviewer,
never a decision.

The model is loaded lazily on first use, runs on the CPU, and all inference
goes through a single worker thread, so the (not thread-safe) model is never
used concurrently. A call that exceeds the timeout or fails raises
`DetectorUnavailable`; callers then return OpenCV-only results.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass

import numpy as np

from app.ai.vision.quality import downscale
from app.core.config import get_settings

logger = logging.getLogger(__name__)

MODEL_LABEL = "yolov8n (COCO)"
# After a failed load, wait this long before trying again.
_RETRY_AFTER_SECONDS = 300


class DetectorUnavailable(Exception):
    """The detector could not be loaded or did not answer in time."""


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in original image pixels


class YoloDetector:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._failed_at: float | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo")

    def _load(self):
        with self._lock:
            if self._model is not None:
                return self._model
            if self._failed_at is not None and time.monotonic() - self._failed_at < _RETRY_AFTER_SECONDS:
                raise DetectorUnavailable("detector failed to load recently")
            settings = get_settings()
            weights = settings.vision_weights_path
            if not weights.is_file() and not settings.vision_allow_weights_download:
                self._failed_at = time.monotonic()
                raise DetectorUnavailable(f"weights file not found: {weights.name}")
            try:
                from ultralytics import YOLO  # heavy import (torch), done lazily

                weights.parent.mkdir(parents=True, exist_ok=True)
                # A missing official weights file is downloaded by ultralytics to this path.
                model = YOLO(str(weights))
                model.to("cpu")
            except Exception as exc:  # noqa: BLE001 - any load failure means "unavailable"
                self._failed_at = time.monotonic()
                logger.warning("yolo model failed to load: %s", exc.__class__.__name__)
                raise DetectorUnavailable(str(exc)) from exc
            self._model = model
            self._failed_at = None
            logger.info("yolo model loaded from %s", weights.name)
            return model

    def _predict(self, image: np.ndarray, confidence: float, max_side: int) -> list[Detection]:
        model = self._load()
        small, scale = downscale(image, max_side)
        results = model.predict(small, conf=confidence, device="cpu", verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = result.names
            boxes = result.boxes
            if boxes is None:
                continue
            for xyxy, conf, cls in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), strict=True):
                x1, y1, x2, y2 = (round(v / scale, 1) for v in xyxy)
                detections.append(
                    Detection(label=str(names[int(cls)]), confidence=round(float(conf), 3), box=(x1, y1, x2, y2))
                )
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def detect(self, image: np.ndarray) -> list[Detection]:
        settings = get_settings()
        if not settings.vision_detector_enabled:
            raise DetectorUnavailable("detector disabled by configuration")
        future = self._executor.submit(
            self._predict, image, settings.vision_confidence_threshold, settings.vision_max_image_side
        )
        try:
            return future.result(timeout=settings.vision_timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            logger.warning("yolo detection timed out after %ss", settings.vision_timeout_seconds)
            raise DetectorUnavailable("detection timed out") from exc
        except DetectorUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("yolo detection failed: %s", exc.__class__.__name__)
            raise DetectorUnavailable(str(exc)) from exc


_instance: YoloDetector | None = None
_instance_lock = threading.Lock()


def get_detector() -> YoloDetector:
    """Process-wide singleton (created on first call, model loaded on first detection)."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = YoloDetector()
    return _instance
