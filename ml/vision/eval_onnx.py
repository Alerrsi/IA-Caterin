"""Evalúa un ONNX con el MISMO código que usa la API (apps/api/app/modules/vision/detector.py).

    python eval_onnx.py --model runs/<version>/onnx --dataset data/snacks-v1 [--split test]

Reporta por clase y total: error absoluto medio de conteo y % de fotos con conteo exacto, por umbral, más la
latencia de punta a punta de `detect` (decodificar + preprocesar + inferir + postprocesar) en esta CPU.
mAP50 y mAP50:95 los entrega RF-DETR en el log de entrenamiento / `evaluate`; aquí solo conteo y latencia.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from app.modules.vision.detector import OnnxDetector  # noqa: E402

THRESHOLDS = (0.3, 0.5, 0.7)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="carpeta con model.onnx y model.json")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    det = OnnxDetector(args.model / "model.onnx", json.loads((args.model / "model.json").read_text()))
    coco = json.loads((args.dataset / args.split / "_annotations.coco.json").read_text())
    names = {c["id"]: c["name"] for c in coco["categories"]}
    truth: dict[int, Counter[str]] = {i["id"]: Counter() for i in coco["images"]}
    for a in coco["annotations"]:
        truth[a["image_id"]][names[a["category_id"]]] += 1

    lat: list[float] = []
    preds: dict[int, list[tuple[str, float]]] = {}
    for img in coco["images"]:
        data = (args.dataset / args.split / img["file_name"]).read_bytes()
        t0 = time.perf_counter()
        dets = det.detect(data, min(THRESHOLDS))
        lat.append((time.perf_counter() - t0) * 1000)
        preds[img["id"]] = [(d.vision_class, d.score) for d in dets]

    result: dict[str, object] = {
        "model": det.info.version,
        "split": args.split,
        "images": len(lat),
        "latency_ms": {"p50": statistics.median(lat), "p95": sorted(lat)[int(0.95 * (len(lat) - 1))]},
    }
    for t in THRESHOLDS:
        per: dict[str, dict[str, float]] = {}
        for cls in det.info.classes:
            err = exact = n = 0
            for iid, gt in truth.items():
                if gt[cls] == 0 and not any(c == cls and s >= t for c, s in preds[iid]):
                    continue  # la foto no tiene esa clase ni se predijo: no cuenta para esa clase
                pred = sum(1 for c, s in preds[iid] if c == cls and s >= t)
                err += abs(pred - gt[cls])
                exact += pred == gt[cls]
                n += 1
            per[cls] = {"photos": n, "mae": err / n if n else float("nan"), "exact_pct": 100 * exact / n if n else float("nan")}
        result[f"threshold_{t}"] = per
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
