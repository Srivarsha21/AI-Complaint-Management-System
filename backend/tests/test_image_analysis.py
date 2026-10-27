"""Image analysis: OpenCV quality checks, mocked detector, endpoints and caching.

The YOLO detector is always mocked here, so no model is downloaded or loaded.
"""

import importlib.util

import pytest

from app.ai.vision import detector as detector_module
from app.ai.vision.detector import Detection, DetectorUnavailable
from app.ai.vision.quality import assess_quality, decode_image, downscale
from app.core.config import get_settings
from app.models import AttachmentAnalysis, UserRole
from app.services import image_analysis
from tests.conftest import auth_header, login, make_category, make_user
from tests.image_factory import CORRUPT_JPEG, CORRUPT_PNG, blurred, checkerboard, encode, solid

ANALYSE = "/api/v1/ai/image-analysis"
COMPLAINTS = "/api/v1/complaints"


class FakeDetector:
    def __init__(self, detections=None, error: Exception | None = None):
        self.detections = detections or []
        self.error = error
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.detections)


@pytest.fixture(autouse=True)
def fake_detector(monkeypatch):
    fake = FakeDetector([Detection(label="dog", confidence=0.91, box=(1.0, 2.0, 30.0, 40.0))])
    monkeypatch.setattr(detector_module, "get_detector", lambda: fake)
    return fake


@pytest.fixture
def citizen(client, db):
    make_user(db, email="citizen@example.com")
    return login(client, "citizen@example.com")


def _quality(image):
    s = get_settings()
    return assess_quality(
        image, blur_threshold=s.vision_blur_threshold, dark_threshold=s.vision_dark_threshold,
        bright_threshold=s.vision_bright_threshold,
    )


# --- OpenCV quality checks -----------------------------------------------------

def test_sharp_checkerboard_is_not_blurry_and_blurred_copy_is():
    sharp = _quality(checkerboard(256, 16))
    soft = _quality(blurred(checkerboard(256, 16), 31))
    assert not sharp.is_blurry
    assert soft.is_blurry
    assert sharp.blur_score > soft.blur_score
    assert (sharp.width, sharp.height) == (256, 256)


def test_brightness_flags():
    dark = _quality(solid(5))
    bright = _quality(solid(250))
    mid = _quality(solid(128))
    assert dark.too_dark and not dark.too_bright
    assert bright.too_bright and not bright.too_dark
    assert not mid.too_dark and not mid.too_bright
    assert dark.brightness == 5.0


def test_decode_rejects_corrupt_bytes_with_valid_magic():
    assert decode_image(CORRUPT_PNG) is None
    assert decode_image(CORRUPT_JPEG) is None
    assert decode_image(b"") is None
    assert decode_image(encode(checkerboard(), ".png")).shape == (128, 128, 3)


def test_downscale_keeps_aspect_ratio():
    import numpy as np

    small, scale = downscale(np.zeros((400, 2000, 3), dtype=np.uint8), 1000)
    assert small.shape[:2] == (200, 1000)
    assert scale == 0.5


def test_category_hints_are_conservative():
    def hints(*labels):
        return {h.slug for h in image_analysis._category_hints([Detection(l, 0.9, (0, 0, 1, 1)) for l in labels])}

    assert hints("dog") == {"stray-animals"}
    assert hints("cow", "car") == {"stray-animals", "roads-potholes"}
    assert hints("fire hydrant") == {"water-supply"}
    assert hints("person", "bench", "potted plant") == set()


# --- POST /ai/image-analysis ---------------------------------------------------

def test_image_analysis_returns_quality_detections_hints_and_disclaimer(client, citizen, fake_detector, _isolated_uploads):
    png = encode(checkerboard(64, 8), ".png")
    response = client.post(ANALYSE, files={"image": ("p.png", png, "image/png")}, headers=auth_header(citizen))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert (body["width"], body["height"]) == (64, 64)
    assert body["is_blurry"] is False
    assert body["detections"] == [{"label": "dog", "confidence": 0.91, "box": [1.0, 2.0, 30.0, 40.0]}]
    assert body["category_hints"][0]["slug"] == "stray-animals"
    assert body["detector_available"] is True
    assert body["model"] == "yolov8n (COCO)"
    assert "cannot recognise potholes" in body["disclaimer"]
    # Nothing is stored.
    assert not (_isolated_uploads / "complaints").exists()


def test_image_analysis_falls_back_to_opencv_when_detector_unavailable(client, citizen, monkeypatch):
    monkeypatch.setattr(detector_module, "get_detector", lambda: FakeDetector(error=DetectorUnavailable("timed out")))
    jpg = encode(solid(5, 32), ".jpg")
    response = client.post(ANALYSE, files={"image": ("d.jpg", jpg, "image/jpeg")}, headers=auth_header(citizen))
    assert response.status_code == 200
    body = response.json()
    assert body["detector_available"] is False
    assert body["detections"] == [] and body["category_hints"] == []
    assert body["too_dark"] is True


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (CORRUPT_PNG, "could not be read as an image"),
        (b"<svg onload=alert(1)>", "not a supported image"),
        (b"", "is empty"),
    ],
)
def test_image_analysis_rejects_invalid_files(client, citizen, content, message):
    response = client.post(ANALYSE, files={"image": ("x.png", content, "image/png")}, headers=auth_header(citizen))
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_image_analysis_rejects_too_many_pixels(client, citizen, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_image_pixels", 100)
    png = encode(checkerboard(64, 8), ".png")
    response = client.post(ANALYSE, files={"image": ("p.png", png, "image/png")}, headers=auth_header(citizen))
    assert response.status_code == 400
    assert "too many pixels" in response.json()["detail"]


def test_image_analysis_requires_login_and_is_rate_limited(client, citizen, monkeypatch):
    png = encode(checkerboard(32, 4), ".png")
    assert client.post(ANALYSE, files={"image": ("p.png", png, "image/png")}).status_code == 401

    monkeypatch.setattr(get_settings(), "ai_rate_limit_attempts", 2)
    codes = [
        client.post(ANALYSE, files={"image": ("p.png", png, "image/png")}, headers=auth_header(citizen)).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


# --- GET /complaints/{id}/attachments/{id}/analysis -----------------------------

def _complaint_with_photo(client, db, tokens):
    category = make_category(db, slug="stray-animals", name="Stray Animals")
    data = {
        "subject": "Stray dogs near school", "description": "A pack of stray dogs chases children every morning.",
        "category_id": str(category.id), "location_text": "Kukatpally, Hyderabad",
    }
    files = [("attachments", ("dog.png", encode(checkerboard(64, 8), ".png"), "image/png"))]
    response = client.post(COMPLAINTS, data=data, files=files, headers=auth_header(tokens))
    assert response.status_code == 201, response.text
    created = response.json()
    return f"{COMPLAINTS}/{created['id']}/attachments/{created['attachments'][0]['id']}/analysis"


def test_attachment_analysis_authorisation(client, db, citizen):
    url = _complaint_with_photo(client, db, citizen)

    assert client.get(url, headers=auth_header(citizen)).status_code == 200
    assert client.get(url).status_code == 401

    make_user(db, email="other@example.com")
    assert client.get(url, headers=auth_header(login(client, "other@example.com"))).status_code == 404

    make_user(db, email="staff@example.com", role=UserRole.ADMIN)
    assert client.get(url, headers=auth_header(login(client, "staff@example.com"))).status_code == 200

    missing = url.replace("/analysis", "").rsplit("/", 1)[0] + "/999999/analysis"
    assert client.get(missing, headers=auth_header(citizen)).status_code == 404


def test_attachment_analysis_is_cached(client, db, citizen, fake_detector):
    url = _complaint_with_photo(client, db, citizen)

    first = client.get(url, headers=auth_header(citizen))
    second = client.get(url, headers=auth_header(citizen))
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert fake_detector.calls == 1

    row = db.query(AttachmentAnalysis).one()
    assert row.model_version == image_analysis.model_version()
    assert row.result["detections"][0]["label"] == "dog"


def test_attachment_analysis_recomputes_when_model_version_changes(client, db, citizen, fake_detector, monkeypatch):
    url = _complaint_with_photo(client, db, citizen)
    client.get(url, headers=auth_header(citizen))
    monkeypatch.setattr(get_settings(), "vision_confidence_threshold", 0.6)
    client.get(url, headers=auth_header(citizen))
    assert fake_detector.calls == 2
    db.expire_all()
    assert db.query(AttachmentAnalysis).one().model_version.endswith("conf=0.6")


def test_opencv_only_results_are_not_cached(client, db, citizen, monkeypatch):
    url = _complaint_with_photo(client, db, citizen)
    failing = FakeDetector(error=DetectorUnavailable("no weights"))
    monkeypatch.setattr(detector_module, "get_detector", lambda: failing)

    body = client.get(url, headers=auth_header(citizen)).json()
    assert body["detector_available"] is False
    client.get(url, headers=auth_header(citizen))
    assert failing.calls == 2
    assert db.query(AttachmentAnalysis).count() == 0


# --- Detector wrapper -----------------------------------------------------------

def test_detector_without_weights_and_download_disabled_is_unavailable(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "vision_weights_dir", str(tmp_path))
    monkeypatch.setattr(settings, "vision_allow_weights_download", False)
    with pytest.raises(DetectorUnavailable):
        detector_module.YoloDetector().detect(solid(0, 8))


def test_detector_disabled_by_setting(monkeypatch):
    monkeypatch.setattr(get_settings(), "vision_detector_enabled", False)
    with pytest.raises(DetectorUnavailable):
        detector_module.YoloDetector().detect(solid(0, 8))


def test_detector_timeout_reports_unavailable(monkeypatch):
    import threading

    release = threading.Event()
    instance = detector_module.YoloDetector()
    monkeypatch.setattr(instance, "_predict", lambda *args: release.wait(5) or [])
    monkeypatch.setattr(get_settings(), "vision_timeout_seconds", 0.05)
    # Independent of the environment (e.g. VISION_DETECTOR_ENABLED=false on small servers).
    monkeypatch.setattr(get_settings(), "vision_detector_enabled", True)
    try:
        with pytest.raises(DetectorUnavailable, match="timed out"):
            instance.detect(solid(0, 8))
    finally:
        release.set()


@pytest.mark.skipif(not get_settings().vision_weights_path.is_file(), reason="YOLO weights not downloaded")
@pytest.mark.skipif(importlib.util.find_spec("ultralytics") is None, reason="ultralytics not installed (deploy requirements)")
def test_real_yolo_model_runs_on_synthetic_image(monkeypatch):
    """Optional integration check; runs only when the weights file already exists (no download)."""
    monkeypatch.setattr(get_settings(), "vision_allow_weights_download", False)
    monkeypatch.setattr(get_settings(), "vision_detector_enabled", True)
    # The first call loads PyTorch, which can exceed the 20 s request limit on a busy machine.
    monkeypatch.setattr(get_settings(), "vision_timeout_seconds", 180)
    detections = detector_module.YoloDetector().detect(checkerboard(320, 40))
    assert isinstance(detections, list)
    assert all(0 <= d.confidence <= 1 for d in detections)
