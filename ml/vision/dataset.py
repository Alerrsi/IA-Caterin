"""Pipeline de datos de visión (T06): división sin fuga y manifiesto con hash. Solo librería estándar.

Entrada:  data/raw/annotations.json (COCO) + data/raw/images/. Cada imagen lleva `"session": "<id>"`
          (la tanda o sesión de fotos); todas las fotos de una sesión caen en el mismo split.
Salida:   data/<version>/{train,valid,test}/ con sus imágenes y `_annotations.coco.json` (layout de RF-DETR)
          y `manifest.json` con semilla, conteos y sha256 de cada archivo.

Uso:  python dataset.py split --version v1 --seed 42
      python dataset.py check data/v1
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


def split(raw: Path, out: Path, seed: int) -> dict[str, Any]:
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
            files[f"{name}/{i['file_name']}"] = sha256_file(d / i["file_name"])
        sub = {
            "images": imgs,
            "annotations": [a for a in coco["annotations"] if a["image_id"] in ids],
            "categories": coco["categories"],
        }
        (d / "_annotations.coco.json").write_text(json.dumps(sub, ensure_ascii=False))
    manifest = build_manifest(out, seed, files)
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
    ck = sub.add_parser("check")
    ck.add_argument("dataset", type=Path)
    args = ap.parse_args()
    if args.cmd == "split":
        m = split(args.raw, Path("data") / args.version, args.seed)
        print(json.dumps({k: v for k, v in m.items() if k != "files"}, ensure_ascii=False, indent=2))
    else:
        problems = check(args.dataset)
        print("\n".join(problems) or "OK: sin fugas, hashes coinciden, todas las clases presentes")
        sys.exit(any(not p.startswith("AVISO") for p in problems))


if __name__ == "__main__":
    main()
