"""Fine-tuning de RF-DETR Nano y export a ONNX (T06). Pensado para Colab o Kaggle con GPU.

    pip install "rfdetr[train,onnx]==1.12.0"
    python train.py --dataset data/snacks-v1 --version snacks-v1-nano-1 --epochs 30

Verifica antes el manifiesto del dataset (sin fugas, hashes). Deja en --out: onnx/model.onnx, onnx/model.json
(versión, clases, tamaño de entrada, sha256 del dataset y del ONNX) y los checkpoints de RF-DETR.
"""

import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path

import numpy as np

import dataset


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--version", required=True, help="identificador del modelo, p. ej. snacks-v1-nano-1")
    ap.add_argument("--out", type=Path, default=Path("runs"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    problems = [p for p in dataset.check(args.dataset) if not p.startswith("AVISO")]
    if problems:
        raise SystemExit("El dataset no pasa la verificación:\n" + "\n".join(problems))
    manifest = json.loads((args.dataset / "manifest.json").read_text())

    import onnxruntime as ort
    import rfdetr
    import torch
    from rfdetr import RFDETRNano

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    run = args.out / args.version
    model = RFDETRNano()
    model.train(
        dataset_dir=str(args.dataset),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        output_dir=str(run),
        seed=args.seed,
    )
    exported = Path(model.export(output_dir=str(run / "onnx")))
    onnx_path = run / "onnx" / "model.onnx"
    if exported != onnx_path:
        shutil.copy2(exported, onnx_path)

    coco = json.loads((args.dataset / "train" / "_annotations.coco.json").read_text())
    classes = [c["name"] for c in sorted(coco["categories"], key=lambda c: c["id"])]
    size = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"]).get_inputs()[0].shape[2]
    meta = {
        "version": args.version,
        "classes": classes,
        "input_size": int(size),
        "onnx_sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        "dataset": manifest["version"],
        "dataset_sha256": manifest["dataset_sha256"],
        "seed": args.seed,
        "epochs": args.epochs,
        "rfdetr": rfdetr.__version__ if hasattr(rfdetr, "__version__") else "1.12.0",
    }
    (run / "onnx" / "model.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
