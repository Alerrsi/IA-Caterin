"""Pipeline de datos de visión (T06): división sin fuga y manifiesto con hash. Solo librería estándar.

Entrada:  data/raw/annotations.json (COCO) + data/raw/images/. Cada imagen lleva `"session": "<id>"`
          (la tanda o sesión de fotos); todas las fotos de una sesión caen en el mismo split.
Salida:   data/<version>/{train,valid,test}/ con sus imágenes y `_annotations.coco.json` (layout de RF-DETR)
          y `manifest.json` con semilla, conteos y sha256 de cada archivo.

Uso:  python dataset.py split --version v1 --seed 42 [--augment 2]
      python dataset.py check data/v1

`--augment N` agrega N copias aumentadas de cada foto de **train** (luz de cocina, ángulo de celular,
desenfoque; ver augment.py). Cada copia hereda la sesión de su original, así que no hay fuga hacia
valid/test. Es lo único que necesita Pillow y NumPy; sin `--augment` basta la librería estándar.
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SPLITS = ("train", "valid", "test")
FRACTIONS = {"train": 0.70, "valid": 0.15, "test": 0.15}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assign_sessions(sizes: dict[str, int], seed: int) -> dict[str, str]:
    """Reparte sesiones enteras a splits acercándose a FRACTIONS por número de imágenes."""
    order = sorted(sizes)
    random.Random(seed).shuffle(order)
    total = sum(sizes.values())
    load = dict.fromkeys(SPLITS, 0)
    out: dict[str, str] = {}
    for sess in sorted(order, key=lambda s: -sizes[s]):  # las grandes primero, para encajar mejor
        target = min(SPLITS, key=lambda s: (load[s] + sizes[sess]) / (FRACTIONS[s] * total) if total else 0)
        out[sess] = target
        load[target] += sizes[sess]
    return out


def augment_train(d: Path, imgs: list[dict[str, Any]], anns: list[dict[str, Any]], copies: int, seed: int) -> None:
    """Agrega en `d` (y en `imgs`/`anns`, en el lugar) `copies` versiones aumentadas de cada imagen."""
    from PIL import Image

    from augment import augment

    next_img = max((i["id"] for i in imgs), default=0) + 1
    next_ann = max((a["id"] for a in anns), default=0) + 1
    by_img: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for a in anns:
        by_img[a["image_id"]].append(a)
    for im in list(imgs):
        src = Image.open(d / im["file_name"])
        stem, ext = Path(im["file_name"]).stem, Path(im["file_name"]).suffix
        own = by_img[im["id"]]
        for k in range(copies):
            img, boxes = augment(src, [tuple(a["bbox"]) for a in own], seed * 100_003 + im["id"] * 101 + k)
            name = f"{stem}_aug{k}{ext}"
            img.save(d / name, quality=90)
            imgs.append({**im, "id": next_img, "file_name": name, "augmented_from": im["file_name"]})
            for a, box in zip(own, boxes, strict=True):
                if box[2] <= 0 or box[3] <= 0:
                    continue  # el objeto salió del cuadro con la transformación
                bbox = [round(float(v), 1) for v in box]
                anns.append({**a, "id": next_ann, "image_id": next_img, "bbox": bbox, "area": round(bbox[2] * bbox[3], 1)})
                next_ann += 1
            next_img += 1


def split(raw: Path, out: Path, seed: int, augment_copies: int = 0) -> dict[str, Any]:
    coco = json.loads((raw / "annotations.json").read_text())
    images = coco["images"]
    missing = [i["file_name"] for i in images if "session" not in i]
    if missing:
        raise SystemExit(f"Faltan 'session' en {len(missing)} imágenes (p. ej. {missing[0]}); no se puede evitar fuga.")
    sizes = Counter(i["session"] for i in images)
    where = assign_sessions(dict(sizes), seed)
    anns: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for a in coco["annotations"]:
        anns[a["image_id"]].append(a)
    if out.exists():
        raise SystemExit(f"{out} ya existe; usa otra --version (las versiones no se sobrescriben).")
    files: dict[str, str] = {}
    for name in SPLITS:
        d = out / name
        d.mkdir(parents=True)
        imgs = [i for i in images if where[i["session"]] == name]
        ids = {i["id"] for i in imgs}
        for i in imgs:
            shutil.copy2(raw / "images" / i["file_name"], d / i["file_name"])
        sub_anns = [a for a in coco["annotations"] if a["image_id"] in ids]
        if name == "train" and augment_copies > 0:
            augment_train(d, imgs, sub_anns, augment_copies, seed)
        for i in imgs:
            files[f"{name}/{i['file_name']}"] = sha256_file(d / i["file_name"])
        sub = {"images": imgs, "annotations": sub_anns, "categories": coco["categories"]}
        (d / "_annotations.coco.json").write_text(json.dumps(sub, ensure_ascii=False))
    manifest = build_manifest(out, seed, files)
    manifest["augment_copies"] = augment_copies
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def build_manifest(out: Path, seed: int, files: dict[str, str]) -> dict[str, Any]:
    cats: dict[int, str] = {}
    per_split: dict[str, Any] = {}
    for name in SPLITS:
        coco = json.loads((out / name / "_annotations.coco.json").read_text())
        cats = {c["id"]: c["name"] for c in coco["categories"]}
        per_split[name] = {
            "images": len(coco["images"]),
            "boxes": Counter(cats[a["category_id"]] for a in coco["annotations"]),
            "sessions": sorted({i["session"] for i in coco["images"]}),
        }
    digest = hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()).hexdigest()
    return {"version": out.name, "seed": seed, "dataset_sha256": digest, "splits": per_split, "files": files}


def check(out: Path) -> list[str]:
    """Devuelve los problemas: fuga entre splits, archivos alterados y clases ausentes en valid/test."""
    manifest = json.loads((out / "manifest.json").read_text())
    problems: list[str] = []
    seen: dict[str, str] = {}
    for name, info in manifest["splits"].items():
        for sess in info["sessions"]:
            if sess in seen:
                problems.append(f"FUGA: la sesión '{sess}' está en {seen[sess]} y en {name}")
            seen[sess] = name
    for rel, expected in manifest["files"].items():
        p = out / rel
        if not p.is_file() or sha256_file(p) != expected:
            problems.append(f"ALTERADO o faltante: {rel}")
    train_classes = set(manifest["splits"]["train"]["boxes"])
    for name in ("valid", "test"):
        for cls in train_classes - set(manifest["splits"][name]["boxes"]):
            problems.append(f"AVISO: la clase '{cls}' no aparece en {name}; sus métricas no son confiables")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("split")
    sp.add_argument("--raw", type=Path, default=Path("data/raw"))
    sp.add_argument("--version", required=True)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--augment", type=int, default=0, help="copias aumentadas por foto de train (0 = ninguna)")
    ck = sub.add_parser("check")
    ck.add_argument("dataset", type=Path)
    args = ap.parse_args()
    if args.cmd == "split":
        m = split(args.raw, Path("data") / args.version, args.seed, args.augment)
        print(json.dumps({k: v for k, v in m.items() if k != "files"}, ensure_ascii=False, indent=2))
    else:
        problems = check(args.dataset)
        print("\n".join(problems) or "OK: sin fugas, hashes coinciden, todas las clases presentes")
        sys.exit(any(not p.startswith("AVISO") for p in problems))


if __name__ == "__main__":
    main()
