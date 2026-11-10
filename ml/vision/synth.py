"""Dataset SINTÉTICO de bandejas para validar el pipeline de F2 de punta a punta.

**No representa fotos reales.** Dibuja empanadas (medialunas doradas con repulgue), canapés (galleta
cuadrada con cobertura) y brochetas (palo con trozos de colores) sobre bandejas con luz variable.
Sirve para probar dataset → split → entrenamiento → ONNX → API → métricas de conteo. Las métricas que
salgan de aquí se reportan como sintéticas en el model card y nunca como del caso real (AGENTS.md, F2).

Cada "sesión" simula una tanda: mismas condiciones de bandeja y luz. El split agrupa por sesión.
La salida tiene el formato de entrada de `dataset.py split` (`annotations.json` + `images/`). Desde ml/vision:

    python synth.py --out data/raw-synth-v1 --sessions 30 --per-session 5
    python dataset.py split --raw data/raw-synth-v1 --version synth-v1 --augment 2
"""

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

CLASSES = ["empanada", "canape", "brocheta"]


def _tray(rnd: random.Random, w: int, h: int) -> Image.Image:
    base = rnd.choice([(170, 170, 175), (140, 100, 65), (225, 225, 220), (60, 60, 65)])  # acero, madera, loza, negra
    img = Image.new("RGB", (w, h), base)
    noise = Image.effect_noise((w, h), rnd.uniform(8, 20)).convert("RGB")
    return Image.blend(img, noise, 0.12)


def _empanada(draw: ImageDraw.ImageDraw, rnd: random.Random, cx: float, cy: float, s: float) -> tuple[float, ...]:
    angle = rnd.uniform(0, 360)
    color = (rnd.randint(190, 225), rnd.randint(130, 165), rnd.randint(55, 85))
    box = (cx - s, cy - s * 0.75, cx + s, cy + s * 0.75)
    draw.pieslice(box, angle, angle + 180, fill=color, outline=(150, 95, 40), width=max(2, int(s / 10)))
    # La caja de la medialuna: tomar los puntos del borde del semicírculo
    pts = [(cx, cy)]
    for k in range(0, 181, 15):
        a = math.radians(angle + k)
        pts.append((cx + s * math.cos(a), cy + s * 0.75 * math.sin(a)))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _canape(draw: ImageDraw.ImageDraw, rnd: random.Random, cx: float, cy: float, s: float) -> tuple[float, ...]:
    h = s * 0.6
    draw.rectangle((cx - h, cy - h, cx + h, cy + h), fill=(225, 195, 140), outline=(180, 150, 100), width=2)
    top = rnd.choice([(230, 110, 90), (90, 150, 80), (250, 240, 220), (120, 40, 50)])  # salmón, palta, queso, aceituna
    r = h * rnd.uniform(0.45, 0.7)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=top)
    return cx - h, cy - h, cx + h, cy + h


def _brocheta(draw: ImageDraw.ImageDraw, rnd: random.Random, cx: float, cy: float, s: float) -> tuple[float, ...]:
    a = math.radians(rnd.uniform(0, 180))
    dx, dy = math.cos(a) * s * 1.4, math.sin(a) * s * 1.4
    draw.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=(200, 170, 120), width=max(2, int(s / 12)))
    chunk = s * 0.28
    for t in (-0.6, -0.2, 0.2, 0.6):
        px, py = cx + dx * t, cy + dy * t
        col = rnd.choice([(200, 40, 40), (240, 200, 60), (120, 160, 60), (160, 90, 60)])
        draw.ellipse((px - chunk, py - chunk, px + chunk, py + chunk), fill=col)
    xs = [cx - dx, cx + dx]
    ys = [cy - dy, cy + dy]
    return min(xs) - chunk, min(ys) - chunk, max(xs) + chunk, max(ys) + chunk


DRAWERS = {"empanada": _empanada, "canape": _canape, "brocheta": _brocheta}


def _overlaps(box: tuple[float, ...], placed: list[tuple[float, ...]], margin: float) -> bool:
    return any(
        not (box[2] + margin < p[0] or p[2] + margin < box[0] or box[3] + margin < p[1] or p[3] + margin < box[1])
        for p in placed
    )


def make_image(rnd: random.Random, session: dict[str, float]) -> tuple[Image.Image, list[dict[str, object]]]:
    w, h = rnd.choice([(800, 600), (1024, 768), (768, 1024)])
    img = _tray(rnd, w, h)
    draw = ImageDraw.Draw(img)
    size = session["size"] * min(w, h)
    weights = [session["w_emp"], session["w_can"], session["w_bro"]]
    placed: list[tuple[float, ...]] = []
    anns: list[dict[str, object]] = []
    for _ in range(rnd.randint(3, 16)):
        cls = rnd.choices(CLASSES, weights)[0]
        s = size * rnd.uniform(0.85, 1.15) * (0.6 if cls == "canape" else 1.0)
        for _try in range(30):
            cx, cy = rnd.uniform(s * 1.5, w - s * 1.5), rnd.uniform(s * 1.5, h - s * 1.5)
            probe = (cx - s * 1.5, cy - s * 1.5, cx + s * 1.5, cy + s * 1.5)
            if not _overlaps(probe, placed, 2):
                placed.append(probe)
                x1, y1, x2, y2 = DRAWERS[cls](draw, rnd, cx, cy, s)
                anns.append({"class": cls, "bbox": [x1, y1, x2 - x1, y2 - y1]})
                break
    # luz de cocina: brillo y temperatura de color de la sesión
    r, g, b = img.split()
    warm = session["warm"]
    img = Image.merge("RGB", (r.point(lambda v: min(255, v * warm)), g, b.point(lambda v: v / warm)))
    img = img.point(lambda v: min(255, int(v * session["bright"])))
    if rnd.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(rnd.uniform(0.5, 1.5)))
    return img, anns


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sessions", type=int, default=30)
    ap.add_argument("--per-session", type=int, default=5)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    images_dir = args.out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(args.seed)
    coco: dict[str, list[dict[str, object]]] = {
        "images": [],
        "annotations": [],
        "categories": [{"id": i + 1, "name": c} for i, c in enumerate(CLASSES)],
    }
    cat_id = {c: i + 1 for i, c in enumerate(CLASSES)}
    for s in range(args.sessions):
        session = {
            "size": rnd.uniform(0.05, 0.09),
            "warm": rnd.uniform(0.9, 1.15),
            "bright": rnd.uniform(0.75, 1.15),
            "w_emp": rnd.uniform(0.2, 1),
            "w_can": rnd.uniform(0.2, 1),
            "w_bro": rnd.uniform(0.2, 1),
        }
        for k in range(args.per_session):
            img, anns = make_image(rnd, session)
            image_id = len(coco["images"]) + 1
            name = f"s{s:03d}_{k:02d}.jpg"
            img.save(images_dir / name, "JPEG", quality=88)
            coco["images"].append(
                {"id": image_id, "file_name": name, "width": img.width, "height": img.height, "session": f"s{s:03d}"}
            )
            for a in anns:
                x, y, bw, bh = (round(float(v), 1) for v in a["bbox"])  # type: ignore[attr-defined]
                coco["annotations"].append(
                    {
                        "id": len(coco["annotations"]) + 1,
                        "image_id": image_id,
                        "category_id": cat_id[str(a["class"])],
                        "bbox": [x, y, bw, bh],
                        "area": round(bw * bh, 1),
                        "iscrowd": 0,
                    }
                )
    (args.out / "annotations.json").write_text(json.dumps(coco))
    (args.out / "SYNTHETIC.txt").write_text("Dataset sintético generado por ml/vision/synth.py. No son fotos reales.\n")
    print(f"{len(coco['images'])} imágenes, {len(coco['annotations'])} objetos en {args.out}")


if __name__ == "__main__":
    main()
