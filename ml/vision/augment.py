"""Augmentations realistas para fotos de bandejas tomadas con celular (T06).

- Luz de cocina: brillo y temperatura de color (fluorescente fría ↔ ampolleta cálida).
- Ángulo de celular: rotación leve, perspectiva leve y espejo horizontal.
- Desenfoque leve (mano que se mueve, foco blando).

Las cajas se transforman llevando sus 4 esquinas por la misma transformación y tomando el rectángulo
que las contiene. Solo se aplican al split de entrenamiento.
"""

import random

import numpy as np
from PIL import Image, ImageFilter

Box = tuple[float, float, float, float]  # x, y, w, h (COCO)


def _photometric(img: Image.Image, rnd: random.Random) -> Image.Image:
    warm = rnd.uniform(0.88, 1.15)
    r, g, b = img.split()
    img = Image.merge("RGB", (r.point(lambda v: min(255, int(v * warm))), g, b.point(lambda v: int(v / warm))))
    bright = rnd.uniform(0.7, 1.25)
    img = img.point(lambda v: min(255, int(v * bright)))
    if rnd.random() < 0.35:
        img = img.filter(ImageFilter.GaussianBlur(rnd.uniform(0.4, 1.4)))
    return img


def _coeffs(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> np.ndarray:
    """Coeficientes de perspectiva que llevan `dst` → `src` (lo que pide PIL.Image.transform)."""
    rows = []
    for (x, y), (u, v) in zip(dst, src, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(rows, dtype=np.float64)
    b = np.array([c for p in src for c in p], dtype=np.float64)
    return np.linalg.solve(a, b)


def _apply(coeffs: np.ndarray, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f, g, h = coeffs
    den = g * x + h * y + 1
    return (a * x + b * y + c) / den, (d * x + e * y + f) / den


def _geometric(img: Image.Image, boxes: list[Box], rnd: random.Random) -> tuple[Image.Image, list[Box]]:
    w, h = img.size
    corners = [(0.0, 0.0), (float(w), 0.0), (float(w), float(h)), (0.0, float(h))]
    # Destino: esquinas movidas levemente (perspectiva) y rotadas en torno al centro.
    jitter = 0.06
    moved = [(x + rnd.uniform(-jitter, jitter) * w, y + rnd.uniform(-jitter, jitter) * h) for x, y in corners]
    ang = np.radians(rnd.uniform(-12, 12))
    cx, cy = w / 2, h / 2
    dst = [
        (cx + (x - cx) * np.cos(ang) - (y - cy) * np.sin(ang), cy + (x - cx) * np.sin(ang) + (y - cy) * np.cos(ang))
        for x, y in moved
    ]
    inverse = _coeffs(corners, dst)  # salida → entrada (para PIL)
    forward = _coeffs(dst, corners)  # entrada → salida (para las cajas)
    out = img.transform((w, h), Image.Transform.PERSPECTIVE, tuple(inverse), Image.Resampling.BILINEAR)
    new_boxes: list[Box] = []
    for bx, by, bw, bh in boxes:
        pts = [_apply(forward, px, py) for px, py in ((bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh))]
        xs = [min(max(p[0], 0.0), w) for p in pts]
        ys = [min(max(p[1], 0.0), h) for p in pts]
        nb = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        new_boxes.append(nb if nb[2] > 2 and nb[3] > 2 else (0.0, 0.0, 0.0, 0.0))
    if rnd.random() < 0.5:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        new_boxes = [(w - x - bw, y, bw, bh) if bw else (x, y, bw, bh) for x, y, bw, bh in new_boxes]
    return out, new_boxes


def augment(img: Image.Image, boxes: list[Box], seed: int) -> tuple[Image.Image, list[Box]]:
    """Devuelve la imagen aumentada y sus cajas. Una caja (0, 0, 0, 0) significa que salió del cuadro."""
    rnd = random.Random(seed)
    out, new_boxes = _geometric(img.convert("RGB"), boxes, rnd)
    return _photometric(out, rnd), new_boxes
