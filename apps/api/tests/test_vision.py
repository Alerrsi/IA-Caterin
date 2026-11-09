"""F2: preprocesamiento, postprocesamiento, conteo por receta y confirmación idempotente."""

import io
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProductionRecord, Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.vision.detector import (
    Detection,
    InvalidImageError,
    ModelInfo,
    get_detector,
    postprocess,
    preprocess,
)
from tests.helpers import assert_isolated, login, register

API = "/api/v1"


def _jpeg(size: tuple[int, int] = (64, 32), exif_orientation: int | None = None) -> bytes:
    img = Image.new("RGB", size, (200, 120, 40))
    exif = Image.Exif()
    if exif_orientation:
        exif[0x0112] = exif_orientation
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


# --------------------------------------------------------------------------- unitarias


def test_preprocess_shape_and_dtype() -> None:
    t = preprocess(_jpeg(), 384)
    assert t.shape == (1, 3, 384, 384) and t.dtype == np.float32


def test_preprocess_applies_exif_rotation_before_dropping_it() -> None:
    # Orientación 6 = girar 90°: una foto de 64x32 queda vertical; con 8 píxeles cuadrados se nota el cambio.
    img = Image.new("RGB", (4, 2))
    img.putpixel((0, 0), (255, 0, 0))  # esquina superior izquierda roja
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, "PNG", exif=exif)
    rotated = preprocess(buf.getvalue(), 8)
    plain = preprocess(_jpeg_from(img), 8)
    assert not np.allclose(rotated, plain)


def _jpeg_from(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_preprocess_rejects_garbage() -> None:
    with pytest.raises(InvalidImageError):
        preprocess(b"no soy una imagen", 384)


def test_postprocess_threshold_boxes_and_order() -> None:
    boxes = np.array([[[0.5, 0.5, 0.2, 0.2], [0.1, 0.1, 0.4, 0.4], [0.9, 0.9, 0.1, 0.1]]], dtype=np.float32)
    logits = np.array([[[4.0, -5.0], [-5.0, 2.0], [-5.0, -5.0]]], dtype=np.float32)  # el 3.º no pasa el umbral
    dets = postprocess(boxes, logits, ["empanada", "canape"], 0.5)
    assert [d.vision_class for d in dets] == ["empanada", "canape"]
    assert dets[0].box == pytest.approx((0.4, 0.4, 0.6, 0.6))
    assert dets[1].box[0] == 0.0  # recortada al borde de la imagen


def test_postprocess_class_count_mismatch() -> None:
    with pytest.raises(ValueError, match="clases"):
        postprocess(np.zeros((1, 1, 4), np.float32), np.zeros((1, 1, 3), np.float32), ["a"], 0.5)


# --------------------------------------------------------------------------- API


class FakeDetector:
    info = ModelInfo(version="fake-1", classes=["empanada", "canape"], input_size=384, sha256="0" * 64)

    def __init__(self, classes: list[str]) -> None:
        self._classes = classes

    def detect(self, image_bytes: bytes, threshold: float) -> list[Detection]:
        preprocess(image_bytes, 32)  # valida la imagen igual que el detector real
        return [Detection(c, 0.9, (0.1, 0.1, 0.2, 0.2)) for c in self._classes]


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict:  # type: ignore[type-arg]
    seed(db)
    recipe = db.scalars(select(Recipe).where(Recipe.is_final_product.is_(True))).first()
    assert recipe is not None
    recipe.vision_class = "empanada"
    db.commit()
    return {"owner": login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD), "recipe": recipe, "db": db}


def _use(client: TestClient, detector: object) -> None:
    client.app.dependency_overrides[get_detector] = lambda: detector  # type: ignore[attr-defined]


def test_model_not_loaded_gives_503_and_model_endpoint(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    _use(client, None)
    assert client.get(f"{API}/vision/model", headers=demo["owner"]).json() == {
        "loaded": False,
        "version": None,
        "classes": [],
        "input_size": None,
        "sha256": None,
    }
    r = client.post(f"{API}/vision/count", headers=demo["owner"], files={"photo": ("a.jpg", _jpeg())})
    assert r.status_code == 503 and r.json()["code"] == "vision_model_unavailable"


def test_count_maps_classes_to_recipes(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    _use(client, FakeDetector(["empanada"] * 3 + ["canape"]))
    r = client.post(f"{API}/vision/count", headers=demo["owner"], files={"photo": ("a.jpg", _jpeg())})
    assert r.status_code == 200, r.text
    lines = {c["vision_class"]: c for c in r.json()["counts"]}
    assert lines["empanada"]["count"] == 3 and lines["empanada"]["recipe_id"] == str(demo["recipe"].id)
    assert lines["canape"]["count"] == 1 and lines["canape"]["recipe_id"] is None  # sin receta asociada
    assert r.json()["model_version"] == "fake-1"


def test_count_rejects_non_image(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    _use(client, FakeDetector([]))
    r = client.post(f"{API}/vision/count", headers=demo["owner"], files={"photo": ("a.jpg", b"hola")})
    assert r.status_code == 415 and r.json()["code"] == "invalid_image"


def test_count_requires_login(client: TestClient) -> None:
    assert client.post(f"{API}/vision/count", files={"photo": ("a.jpg", _jpeg())}).status_code == 401


def test_confirm_records_correction_and_is_idempotent(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    body = {
        "recipe_id": str(demo["recipe"].id),
        "detected_qty": 12,
        "confirmed_qty": 14,
        "model_version": "fake-1",
        "detections": [{"vision_class": "empanada", "score": 0.9, "box": [0.1, 0.1, 0.2, 0.2]}],
    }
    h = {**demo["owner"], "Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"{API}/vision/productions", headers=h, json=body)
    again = client.post(f"{API}/vision/productions", headers=h, json=body)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"] and again.json()["replayed"] is True
    assert first.json()["was_corrected"] is True
    rows = demo["db"].scalars(select(ProductionRecord)).all()
    assert len(rows) == 1 and rows[0].detected_qty == 12 and rows[0].confirmed_qty == 14
    assert rows[0].detections["items"][0]["vision_class"] == "empanada"


def test_confirm_unknown_recipe_and_negative_qty(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    r = client.post(
        f"{API}/vision/productions", headers=demo["owner"], json={"recipe_id": str(uuid.uuid4()), "confirmed_qty": 1}
    )
    assert r.status_code == 404
    r = client.post(
        f"{API}/vision/productions",
        headers=demo["owner"],
        json={"recipe_id": str(demo["recipe"].id), "confirmed_qty": -1},
    )
    assert r.status_code == 422


def test_other_pyme_cannot_confirm_on_my_recipe(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    intruder = register(client, "Otra Pyme", "otra@demo.local")
    assert_isolated(
        client, intruder, "POST", f"{API}/vision/productions", {"recipe_id": str(demo["recipe"].id), "confirmed_qty": 5}
    )
