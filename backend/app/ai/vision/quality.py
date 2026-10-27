"""OpenCV image decoding and quality checks.

Blur metric: variance of the Laplacian of the grayscale image (Pech-Pacheco et
al., 2000). The Laplacian responds to edges; a sharp photo has many strong
edges and therefore a high variance, a blurred one a low variance. The score
depends on resolution, so it is computed after downscaling the image so its
longer side is at most `QUALITY_MAX_SIDE` pixels. The default threshold of
100 (setting VISION_BLUR_THRESHOLD) is a widely used empirical starting point,
not a calibrated value: textureless scenes (a clear sky, a plain wall) can
score low while being in focus, so "blurry" is shown as a warning only.

Brightness is the mean grayscale intensity (0-255). Means below
VISION_DARK_THRESHOLD (default 50) or above VISION_BRIGHT_THRESHOLD
(default 215) are flagged as too dark / too bright.
"""

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np

QUALITY_MAX_SIDE = 1024


@dataclass(frozen=True)
class QualityReport:
    width: int
    height: int
    blur_score: float
    is_blurry: bool
    brightness: float
    too_dark: bool
    too_bright: bool


def image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read width/height from the image header without decoding the pixels."""
    from PIL import Image  # Pillow ships with ultralytics

    try:
        with Image.open(BytesIO(data)) as img:
            return img.size
    except Exception:  # noqa: BLE001 - any parse failure means "not a readable image"
        return None


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode bytes to a BGR array, or None if OpenCV cannot read them."""
    if not data:
        return None
    buffer = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0 or image.ndim != 3:
        return None
    return image


def downscale(image: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """Shrink so the longer side is <= max_side. Returns (image, scale applied)."""
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image, 1.0
    scale = max_side / longest
    resized = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    return resized, scale


def assess_quality(
    image: np.ndarray, *, blur_threshold: float, dark_threshold: float, bright_threshold: float
) -> QualityReport:
    height, width = image.shape[:2]
    small, _ = downscale(image, QUALITY_MAX_SIDE)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    return QualityReport(
        width=int(width),
        height=int(height),
        blur_score=round(blur_score, 2),
        is_blurry=blur_score < blur_threshold,
        brightness=round(brightness, 2),
        too_dark=brightness < dark_threshold,
        too_bright=brightness > bright_threshold,
    )
