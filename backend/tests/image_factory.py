"""Synthetic test images generated in memory (no files, no network)."""

import cv2
import numpy as np


def checkerboard(size: int = 128, square: int = 8) -> np.ndarray:
    """A sharp black/white checkerboard (BGR): high Laplacian variance."""
    tiles = (np.indices((size, size)) // square).sum(axis=0) % 2
    gray = (tiles * 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def blurred(image: np.ndarray, ksize: int = 31) -> np.ndarray:
    return cv2.GaussianBlur(image, (ksize, ksize), 0)


def solid(value: int, size: int = 64) -> np.ndarray:
    return np.full((size, size, 3), value, dtype=np.uint8)


def encode(image: np.ndarray, ext: str = ".png") -> bytes:
    ok, buffer = cv2.imencode(ext, image)
    assert ok
    return buffer.tobytes()


PNG = encode(checkerboard(32, 4), ".png")
JPEG = encode(checkerboard(32, 4), ".jpg")
# Valid magic numbers followed by garbage: passes the header check, fails decoding.
CORRUPT_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
CORRUPT_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
