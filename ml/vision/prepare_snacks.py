"""Convierte Snacks (Open Images, CC BY) a COCO en data/raw para validar el pipeline de F2.

NO representa el producto final: son fotos de comida de internet, no bandejas de una pyme. Sus métricas no se
presentan como del caso real (AGENTS.md §10). Fuentes: huggingface.co/datasets/Matthijs/snacks-detection (cajas,
CC BY 4.0) y Matthijs/snacks (imágenes y créditos, CC BY 2.0). Las fotos se bajan a data/_snacks (no se commitea).

Uso: python prepare_snacks.py [clase ...]     (por defecto: cookie muffin doughnut pretzel)
"""

import csv
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

SRC = Path("data/_snacks")
OUT = Path("data/raw")
DEFAULT = ["cookie", "muffin", "doughnut", "pretzel"]


def main(classes: list[str]) -> None:
    boxes: dict[str, list[dict[str, str]]] = defaultdict(list)
    for split in ("train", "val", "test"):
        for r in csv.DictReader((SRC / f"{split}.csv").open()):
            if r["class_name"] in classes:
                boxes[r["image_id"]].append(r)
    credits = {r["ImageID"]: r for r in csv.DictReader((SRC / "credits.csv").open())}
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    zf = zipfile.ZipFile(SRC / "images.zip")
    in_zip = {Path(n).stem: n for n in zf.namelist() if n.endswith(".jpg") and "MACOSX" not in n}

    cats = [{"id": i, "name": c} for i, c in enumerate(classes)]
    cat_id = {c: i for i, c in enumerate(classes)}
    images, anns, used = [], [], []
    for image_id in sorted(boxes):
        if image_id not in in_zip or image_id not in credits:
            continue
        dest = OUT / "images" / f"{image_id}.jpg"
        dest.write_bytes(zf.read(in_zip[image_id]))
        with Image.open(dest) as im:
            w, h = im.size
        n = len(images) + 1
        images.append(
            {"id": n, "file_name": dest.name, "width": w, "height": h, "session": credits[image_id]["AuthorProfileURL"]}
        )
        for r in boxes[image_id]:
            x1, x2 = sorted((float(r["x_min"]) * w, float(r["x_max"]) * w))
            y1, y2 = sorted((float(r["y_min"]) * h, float(r["y_max"]) * h))
            if x2 - x1 < 2 or y2 - y1 < 2:
                continue
            anns.append(
                {
                    "id": len(anns) + 1,
                    "image_id": n,
                    "category_id": cat_id[r["class_name"]],
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": 0,
                }
            )
        used.append(credits[image_id])
    (OUT / "annotations.json").write_text(json.dumps({"images": images, "annotations": anns, "categories": cats}))
    with (OUT / "CREDITS.csv").open("w", newline="") as f:
        w_ = csv.writer(f)
        w_.writerow(["file", "author", "title", "source", "license"])
        w_.writerows((f"{u['ImageID']}.jpg", u["Author"], u["Title"], u["OriginalLandingURL"], u["License"]) for u in used)
    print(f"{len(images)} imágenes, {len(anns)} cajas, {len({i['session'] for i in images})} autores (sesiones)")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
