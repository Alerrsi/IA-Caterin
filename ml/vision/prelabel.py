"""Pre-etiquetado con Grounding DINO (Apache 2.0) para ahorrar tiempo de etiquetado (T06).

Sugiere cajas a partir de un texto por clase ("empanada", "canapé"...) y escribe un COCO que se importa
en CVAT o Label Studio para que una persona **revise y corrija**. Nada de esto va a producción ni se usa
como verdad sin revisión humana.

    env/bin/python ml/vision/prelabel.py --images fotos/tanda-01 --out fotos/tanda-01/prelabel.coco.json \
        --classes empanada canape brocheta --prompts "empanada" "canapé . bocadito" "brocheta . anticucho"

Modelo: IDEA-Research/grounding-dino-tiny (Apache 2.0), se descarga de Hugging Face la primera vez.
"""

import argparse
import json
import time
from pathlib import Path

MODEL_ID = "IDEA-Research/grounding-dino-tiny"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--classes", nargs="+", required=True, help="nombres de clase (vision_class)")
    ap.add_argument("--prompts", nargs="+", help="texto para cada clase; por defecto el nombre")
    ap.add_argument("--box-threshold", type=float, default=0.3)
    ap.add_argument("--text-threshold", type=float, default=0.25)
    ap.add_argument("--revision", default="main", help="fijar un commit de HF para reproducibilidad")
    args = ap.parse_args()
    prompts = args.prompts or args.classes
    if len(prompts) != len(args.classes):
        ap.error("--prompts debe tener un texto por clase")

    import torch
    from PIL import Image
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=args.revision)  # nosec - revisión fijable
    model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID, revision=args.revision).eval()

    coco: dict[str, list[dict[str, object]]] = {
        "images": [],
        "annotations": [],
        "categories": [{"id": i + 1, "name": c} for i, c in enumerate(args.classes)],
    }
    files = sorted(p for p in args.images.iterdir() if p.suffix.lower() in EXTS)
    start = time.time()
    for path in files:
        img = Image.open(path).convert("RGB")
        image_id = len(coco["images"]) + 1
        coco["images"].append({"id": image_id, "file_name": path.name, "width": img.width, "height": img.height})
        for cid, text in enumerate(prompts, start=1):
            inputs = processor(images=img, text=f"{text}.", return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
            res = processor.post_process_grounded_object_detection(
                outputs,
                inputs.input_ids,
                threshold=args.box_threshold,
                text_threshold=args.text_threshold,
                target_sizes=[(img.height, img.width)],
            )[0]
            for box, score in zip(res["boxes"].tolist(), res["scores"].tolist(), strict=True):
                x1, y1, x2, y2 = box
                coco["annotations"].append(
                    {
                        "id": len(coco["annotations"]) + 1,
                        "image_id": image_id,
                        "category_id": cid,
                        "bbox": [round(x1, 1), round(y1, 1), round(x2 - x1, 1), round(y2 - y1, 1)],
                        "area": round((x2 - x1) * (y2 - y1), 1),
                        "iscrowd": 0,
                        "score": round(score, 3),
                        "source": "grounding-dino-tiny (sin revisar)",
                    }
                )
    args.out.write_text(json.dumps(coco, ensure_ascii=False))
    print(f"{len(files)} imágenes, {len(coco['annotations'])} cajas sugeridas en {time.time() - start:.0f} s → {args.out}")
    print("Importa el archivo en CVAT o Label Studio y revisa cada caja antes de entrenar.")


if __name__ == "__main__":
    main()
