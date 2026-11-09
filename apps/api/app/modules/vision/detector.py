"""Detector de productos (F2): preprocesamiento, inferencia ONNX y postprocesamiento.

Supuesto a verificar al exportar el modelo real (T06, paso de fine-tuning): el ONNX de RF-DETR entrega
primero las cajas (1, N, 4) como cx, cy, w, h normalizadas y después los logits (1, N, C), y las C
columnas coinciden en orden con `classes` del archivo `model.json` junto al ONNX.
"""

import hashlib
import io
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
Image.MAX_IMAGE_PIXELS = 60_000_000  # sobre esto Pillow lanza DecompressionBombError


class InvalidImageError(ValueError):
    pass


@dataclass(frozen=True)
class Detection:
    vision_class: str
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 normalizadas (0 a 1)


@dataclass(frozen=True)
class ModelInfo:
    version: str
    classes: list[str]
    input_size: int
    sha256: str


class Detector(Protocol):
    info: ModelInfo

    def detect(self, image_bytes: bytes, threshold: float) -> list[Detection]: ...


def preprocess(image_bytes: bytes, size: int) -> NDArray[np.float32]:
    """Bytes -> tensor (1, 3, size, size). Aplica la orientación EXIF y luego la descarta."""
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
        img = img.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("No se pudo leer la imagen") from exc
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - _MEAN) / _STD
    return np.ascontiguousarray(arr.transpose(2, 0, 1)[None], dtype=np.float32)


def postprocess(
    boxes: NDArray[np.float32], logits: NDArray[np.float32], classes: list[str], threshold: float
) -> list[Detection]:
    """Cajas cxcywh + logits -> detecciones sobre el umbral, ordenadas por confianza."""
    if logits.shape[-1] != len(classes):
        raise ValueError(f"El modelo tiene {logits.shape[-1]} clases y model.json declara {len(classes)}")
    probs = 1.0 / (1.0 + np.exp(-logits[0]))
    best = probs.argmax(axis=1)
    scores = probs[np.arange(len(best)), best]
    out: list[Detection] = []
    for i in np.flatnonzero(scores >= threshold):
        cx, cy, w, h = (float(v) for v in boxes[0][i])
        box = (max(cx - w / 2, 0.0), max(cy - h / 2, 0.0), min(cx + w / 2, 1.0), min(cy + h / 2, 1.0))
        out.append(Detection(classes[int(best[i])], float(scores[i]), box))
    return sorted(out, key=lambda d: -d.score)


class OnnxDetector:
    def __init__(self, onnx_path: Path, meta: dict[str, object]) -> None:
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name
        self.info = ModelInfo(
            version=str(meta["version"]),
            classes=[str(c) for c in meta["classes"]],  # type: ignore[attr-defined]
            input_size=int(meta["input_size"]),  # type: ignore[call-overload]
            sha256=hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        )

    def detect(self, image_bytes: bytes, threshold: float) -> list[Detection]:
        tensor = preprocess(image_bytes, self.info.input_size)
        outputs = self._session.run(None, {self._input: tensor})
        return postprocess(outputs[0], outputs[1], self.info.classes, threshold)


@lru_cache
def load_detector() -> Detector | None:
    """Carga el ONNX una sola vez; None si no hay modelo (la API responde 503 en /vision/count)."""
    path = get_settings().vision_model_path
    meta_path = path.with_name("model.json")
    if not path.is_file() or not meta_path.is_file():
        logger.warning("modelo de visión no encontrado", extra={"path": str(path)})
        return None
    return OnnxDetector(path, json.loads(meta_path.read_text()))


def get_detector() -> Detector | None:
    """Dependencia de FastAPI; en pruebas se reemplaza con `app.dependency_overrides`."""
    return load_detector()
