#!/usr/bin/env python3
"""Verifica que los modelos instalados coincidan con models.lock.yaml.

Uso:
    python scripts/verify_models.py                 # revisa todo; falla solo si falta un modelo `required`
    python scripts/verify_models.py --ollama-url http://localhost:11434
    python scripts/verify_models.py --strict        # falla también por modelos opcionales

Requiere PyYAML (incluido en el entorno de la API). Ollama: compara el digest local con el fijado.
ONNX: compara sha256 del archivo. Hugging Face: solo informa la revisión fijada.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ollama_models(url: str) -> dict[str, str] | None:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=5) as resp:  # noqa: S310
            data = json.loads(resp.read())
    except OSError:
        return None
    return {m["name"]: m.get("digest", "") for m in data.get("models", [])}


def check(entry: dict[str, Any], ollama: dict[str, str] | None) -> tuple[str, str]:
    source = entry["source"]
    if source == "ollama":
        if ollama is None:
            return "missing", "Ollama no responde"
        name = entry["id"] if ":" in entry["id"] else f"{entry['id']}:latest"
        if name not in ollama:
            return "missing", f"falta en Ollama (ollama pull {entry['id']})"
        want = (entry.get("digest") or "").removeprefix("sha256:")
        if want and ollama[name] != want:
            return "mismatch", f"digest {ollama[name][:12]} ≠ fijado {want[:12]}"
        return "ok", "digest coincide" if want else "presente (digest aún no fijado)"
    if source == "onnx":
        path = ROOT / entry["path"]
        if not path.exists():
            return "missing", f"no existe {entry['path']}"
        got = sha256_of(path)
        if got != entry["sha256"]:
            return "mismatch", f"sha256 {got[:12]} ≠ fijado {entry['sha256'][:12]}"
        return "ok", "sha256 coincide"
    return "ok", f"revisión fijada {entry.get('revision')}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lock", default=str(ROOT / "models.lock.yaml"))
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    lock = yaml.safe_load(Path(args.lock).read_text(encoding="utf-8"))
    ollama = ollama_models(args.ollama_url)
    failed = False
    for entry in lock["models"]:
        status, detail = check(entry, ollama)
        required = bool(entry.get("required"))
        mark = {"ok": "✔", "missing": "✘", "mismatch": "≠"}[status]
        print(f"{mark} {entry['id']:<26} [{entry['license']}] {'obligatorio' if required else 'opcional':<11} {detail}")
        if status != "ok" and (required or args.strict):
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
