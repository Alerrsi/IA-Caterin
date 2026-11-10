"""Cuenta las fotos de `fotos-prueba/` con un modelo ONNX y las compara con `conteos.csv` (F2, T06).

Usa el MISMO detector que la API (apps/api/app/modules/vision/detector.py), así lo que se mide aquí es lo que verá
la usuaria en "Contar con foto". Las fotos son SINTÉTICAS: el resultado no representa fotos reales.

    python count_test_photos.py --model runs/<modelo>/onnx [--threshold 0.5] [--out runs/<modelo>/fotos_prueba.json]
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from app.modules.vision.detector import OnnxDetector  # noqa: E402

PHOTOS = Path(__file__).parent / "fotos-prueba"
PRODUCTS = {"empanadas": "empanada", "canapes": "canape", "brochetas": "brocheta"}  # columna -> prefijo de clase


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True, help="carpeta con model.onnx y model.json")
    ap.add_argument("--threshold", type=float, default=0.5, help="umbral de confianza (el de la API por defecto)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    detector = OnnxDetector(args.model / "model.onnx", json.loads((args.model / "model.json").read_text()))
    rows = list(csv.DictReader((PHOTOS / "conteos.csv").open(encoding="utf-8"), delimiter=";"))
    results, abs_err, exact = [], 0, 0
    for row in rows:
        found = Counter(d.vision_class for d in detector.detect((PHOTOS / row["archivo"]).read_bytes(), args.threshold))
        got = {col: sum(n for cls, n in found.items() if cls.startswith(prefix)) for col, prefix in PRODUCTS.items()}
        want = {col: int(row[col]) for col in PRODUCTS}
        err = sum(abs(got[c] - want[c]) for c in PRODUCTS)
        abs_err += err
        exact += err == 0
        results.append({"archivo": row["archivo"], "esperado": want, "contado": got, "error": err})
        print(f"{'OK ' if err == 0 else 'MAL'} {row['archivo']:28} esperado={want} contado={got}")
    summary = {
        "fotos": len(rows),
        "conteo_exacto": exact,
        "error_absoluto_medio_por_foto": round(abs_err / len(rows), 2),
        "umbral": args.threshold,
        "modelo": detector.info.version,
        "nota": "Fotos SINTÉTICAS (synth.py): no representan fotos reales de bandejas.",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        args.out.write_text(json.dumps({"summary": summary, "fotos": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
