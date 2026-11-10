"""mAP por clase y matriz de confusión del detector ONNX (T06/T10).

Complementa a `eval_onnx.py` (conteo y latencia por umbral). Usa **el mismo código de inferencia que la
API** (`apps/api/app/modules/vision/detector.py`), así que las métricas reflejan lo que verá la usuaria.

Métricas por clase: AP50, AP50:95 (interpolación de 101 puntos, estilo COCO) y error absoluto medio de
conteo (MAE); por foto, % con conteo exacto en todas las clases. Matriz de confusión con emparejamiento
IoU ≥ 0.5 sin mirar la clase. Latencia de `detect` de punta a punta en esta CPU.

    python evaluate.py --model runs/<version>/onnx --dataset data/<version> [--split test] [--out eval.json]
"""

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from app.modules.vision.detector import Detection, OnnxDetector  # noqa: E402

IOU_THRESHOLDS = np.linspace(0.5, 0.95, 10)


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def average_precision(preds: list[tuple[int, float, tuple[float, ...]]], gts: dict[int, list[tuple[float, ...]]], thr: float) -> float:
    """AP de una clase a un umbral de IoU. `preds`: (imagen, puntaje, caja)."""
    n_gt = sum(len(v) for v in gts.values())
    if n_gt == 0:
        return float("nan")
    used = {k: [False] * len(v) for k, v in gts.items()}
    tp: list[int] = []
    for img, _score, box in sorted(preds, key=lambda p: -p[1]):
        best, best_j = 0.0, -1
        for j, g in enumerate(gts.get(img, [])):
            o = iou(box, g)
            if o > best and not used[img][j]:
                best, best_j = o, j
        if best >= thr:
            used[img][best_j] = True
            tp.append(1)
        else:
            tp.append(0)
    if not tp:
        return 0.0
    ctp = np.cumsum(tp)
    recall = ctp / n_gt
    precision = ctp / np.arange(1, len(tp) + 1)
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    points = np.linspace(0, 1, 101)
    idx = np.searchsorted(recall, points, side="left")
    return float(np.mean([precision[i] if i < len(precision) else 0.0 for i in idx]))


def confusion(classes: list[str], gt: list[tuple[str, tuple[float, ...]]], pred: list[Detection]) -> dict[str, dict[str, int]]:
    labels = [*classes, "fondo"]
    m = {r: dict.fromkeys(labels, 0) for r in labels}
    pairs = sorted(
        ((iou(g[1], p.box), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)), reverse=True
    )
    gi, pj = set(), set()
    for o, i, j in pairs:
        if o < 0.5:
            break
        if i in gi or j in pj:
            continue
        gi.add(i)
        pj.add(j)
        m[gt[i][0]][pred[j].vision_class] += 1
    for i, g in enumerate(gt):
        if i not in gi:
            m[g[0]]["fondo"] += 1
    for j, p in enumerate(pred):
        if j not in pj:
            m["fondo"][p.vision_class] += 1
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="carpeta con model.onnx y model.json")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--threshold", type=float, default=0.5, help="umbral del conteo (el de la API)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    det = OnnxDetector(args.model / "model.onnx", json.loads((args.model / "model.json").read_text()))
    split_dir = args.dataset / args.split
    coco = json.loads((split_dir / "_annotations.coco.json").read_text())
    cat = {c["id"]: c["name"] for c in coco["categories"]}
    classes = det.info.classes
    images = {im["id"]: im for im in coco["images"]}

    gts: dict[str, dict[int, list[tuple[float, ...]]]] = defaultdict(lambda: defaultdict(list))
    gt_by_img: dict[int, list[tuple[str, tuple[float, ...]]]] = defaultdict(list)
    for a in coco["annotations"]:
        im = images[a["image_id"]]
        x, y, w, h = a["bbox"]
        box = (x / im["width"], y / im["height"], (x + w) / im["width"], (y + h) / im["height"])
        gts[cat[a["category_id"]]][a["image_id"]].append(box)
        gt_by_img[a["image_id"]].append((cat[a["category_id"]], box))

    preds_ap: dict[str, list[tuple[int, float, tuple[float, ...]]]] = defaultdict(list)
    abs_err: dict[str, list[int]] = defaultdict(list)
    exact = 0
    latencies: list[float] = []
    labels = [*classes, "fondo"]
    conf_total = {r: dict.fromkeys(labels, 0) for r in labels}
    for im in coco["images"]:
        data = (split_dir / im["file_name"]).read_bytes()
        t0 = time.perf_counter()
        low = det.detect(data, 0.05)  # puntaje bajo para la curva de precisión/recall
        latencies.append((time.perf_counter() - t0) * 1000)
        for d in low:
            preds_ap[d.vision_class].append((im["id"], d.score, d.box))
        counted = [d for d in low if d.score >= args.threshold]
        all_ok = True
        for c in classes:
            n_pred = sum(1 for d in counted if d.vision_class == c)
            n_gt = sum(1 for g in gt_by_img[im["id"]] if g[0] == c)
            abs_err[c].append(abs(n_pred - n_gt))
            all_ok &= n_pred == n_gt
        exact += all_ok
        m = confusion(classes, [g for g in gt_by_img[im["id"]] if g[0] in classes], counted)
        for r in m:
            for k in m[r]:
                conf_total[r][k] += m[r][k]

    per_class: dict[str, Any] = {}
    for c in classes:
        aps = [average_precision(preds_ap[c], gts[c], t) for t in IOU_THRESHOLDS]
        per_class[c] = {
            "objects": sum(len(v) for v in gts[c].values()),
            "AP50": round(aps[0], 4),
            "AP50_95": round(float(np.nanmean(aps)), 4),
            "count_MAE": round(statistics.mean(abs_err[c]), 3),
        }
    lat = sorted(latencies)
    result = {
        "model_version": det.info.version,
        "dataset": str(args.dataset),
        "split": args.split,
        "images": len(coco["images"]),
        "threshold": args.threshold,
        "mAP50": round(float(np.nanmean([v["AP50"] for v in per_class.values()])), 4),
        "mAP50_95": round(float(np.nanmean([v["AP50_95"] for v in per_class.values()])), 4),
        "count_MAE": round(statistics.mean(e for v in abs_err.values() for e in v), 3),
        "exact_count_pct": round(100 * exact / len(coco["images"]), 1),
        "per_class": per_class,
        "confusion_matrix": {"rows": "real", "cols": "predicho", "data": conf_total},
        "detect_ms": {
            "p50": round(statistics.median(lat), 1),
            "p95": round(lat[min(len(lat) - 1, round(0.95 * (len(lat) - 1)))], 1),
        },
    }
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
