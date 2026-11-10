"""Curva de aprendizaje: rendimiento vs. número de fotos de entrenamiento (T06/T10).

Para cada tamaño N toma N fotos originales de train (con sus copias aumentadas, si las hay), entrena con
los mismos parámetros (`train.py`) y evalúa sobre el MISMO test (`evaluate.py`). Sirve para decidir cuántas
fotos reales pedir en vez de suponer una cifra (AGENTS.md, F2). Pensado para GPU (Colab/Kaggle). Desde ml/vision:

    python learning_curve.py --dataset data/synth-v1 --sizes 20 50 100 --epochs 6 --out runs/curve-synth-v1
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import dataset as dataset_mod

HERE = Path(__file__).resolve().parent


def subset(dataset: Path, out: Path, n: int, seed: int) -> None:
    if out.exists():
        shutil.rmtree(out)
    for split in ("valid", "test"):
        shutil.copytree(dataset / split, out / split)
    coco = json.loads((dataset / "train" / "_annotations.coco.json").read_text())
    originals = sorted({im.get("augmented_from", im["file_name"]) for im in coco["images"]})
    keep = set(random.Random(seed).sample(originals, min(n, len(originals))))
    images = [im for im in coco["images"] if im.get("augmented_from", im["file_name"]) in keep]
    ids = {im["id"] for im in images}
    (out / "train").mkdir(parents=True)
    for im in images:
        shutil.copy2(dataset / "train" / im["file_name"], out / "train" / im["file_name"])
    coco["images"] = images
    coco["annotations"] = [a for a in coco["annotations"] if a["image_id"] in ids]
    (out / "train" / "_annotations.coco.json").write_text(json.dumps(coco))
    files = {
        f"{split}/{f.name}": dataset_mod.sha256_file(f)
        for split in dataset_mod.SPLITS
        for f in sorted((out / split).iterdir())
        if f.name != "_annotations.coco.json"
    }
    parent = json.loads((dataset / "manifest.json").read_text())
    manifest = dataset_mod.build_manifest(out, parent["seed"], files)
    manifest["subset_of"] = {"version": parent["version"], "dataset_sha256": parent["dataset_sha256"], "train_photos": n}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--sizes", type=int, nargs="+", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    py = sys.executable
    for n in args.sizes:
        data = args.out / f"data-n{n}"
        version = f"{args.dataset.name}-n{n}"
        subset(args.dataset, data, n, args.seed)
        subprocess.run(  # noqa: S603 - comando local fijo
            [py, str(HERE / "train.py"), "--dataset", str(data), "--version", version, "--out", str(args.out),
             "--epochs", str(args.epochs), "--seed", str(args.seed)],
            check=True,
        )
        model_dir = args.out / version / "onnx"
        eval_path = args.out / version / "eval.json"
        subprocess.run(  # noqa: S603
            [py, str(HERE / "evaluate.py"), "--model", str(model_dir), "--dataset", str(data), "--out", str(eval_path)],
            check=True,
        )
        ev = json.loads(eval_path.read_text())
        keys = ("mAP50", "mAP50_95", "count_MAE", "exact_count_pct")
        rows.append({"train_photos": n, "epochs": args.epochs, **{k: ev[k] for k in keys}})
        (args.out / "curve.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
