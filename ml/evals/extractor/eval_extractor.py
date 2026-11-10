"""Evaluación del extractor de pedidos REAL de la app con varios modelos (T10).

Usa `apps/api/app/modules/quotes/extractor.py` (mismo prompt, schema, reintento y normalización que la API) y
la puntuación campo a campo de `app/modules/quotes/evaluation.py`. Corre dentro de la imagen de la API, en la red
del compose (Ollama no publica su puerto):

    docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo caterin-api \\
        python ml/evals/extractor/eval_extractor.py --models qwen3:4b qwen3:4b-instruct gemma4:e4b \\
        --cases ml/evals/extractor/cases.yaml --out ml/evals/extractor/results.json

`--cases` acepta el YAML reservado de T10 (cases.yaml) o el JSONL de T05 (cases.jsonl). Los pedidos son
SINTÉTICOS. El extractor no tiene campo "cliente": se puntúan invitados, fecha, y por producto receta, cantidad y
unidad, más "sin productos inventados".
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from app.core.llm import OllamaProvider  # noqa: E402
from app.db.seed import AROMOS  # noqa: E402
from app.modules.quotes.evaluation import evaluate_case  # noqa: E402
from app.modules.quotes.extractor import PROMPT_VERSION  # noqa: E402

SCRIPT_VERSION = "1.0.0"


def load_cases(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(yaml.safe_load(path.read_text(encoding="utf-8"))["cases"])


def category(check: str) -> str:
    if check in ("guests", "date", "sin productos inventados"):
        return {"guests": "invitados", "date": "fecha", "sin productos inventados": "sin inventados"}[check]
    return check.rsplit(": ", 1)[-1]  # producto | cantidad | unidad


def totals_by_category(case: dict[str, Any]) -> Counter[str]:
    c: Counter[str] = Counter({"invitados": 1, "fecha": 1, "sin inventados": 1})
    for _recipe, qty, unit in case["items"]:
        c["producto"] += 1
        c["cantidad"] += qty is not None
        c["unidad"] += unit is not None
    return c


def loadavg() -> list[float] | None:
    try:
        return [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
    except OSError:
        return None


def pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, round((len(s) - 1) * p))]


def run_model(model: str, cases: list[dict[str, Any]], host: str) -> dict[str, Any]:
    llm = OllamaProvider(host, model, 300, "10m")
    recipes = {uuid.uuid4(): r.name for r in AROMOS.recipes}
    llm.chat_json("Responde JSON.", "hola", {"type": "object"}, num_predict=5)  # carga el modelo (no se mide)
    before = loadavg()
    results = [evaluate_case(llm, case, recipes) for case in cases]
    after = loadavg()
    ok_cat: Counter[str] = Counter()
    tot_cat: Counter[str] = Counter()
    for case, r in zip(cases, results, strict=True):
        tot = totals_by_category(case)
        tot_cat.update(tot)
        if "error" in r:
            continue  # todo el caso cuenta como fallado
        failed = Counter(category(f) for f in r["failed"])
        ok_cat.update({k: v - failed[k] for k, v in tot.items()})
        print(f"  {model} {r['id']}: {r['fields_ok']}/{r['fields_total']} {r['failed']}", file=sys.stderr)
    lat = [r["llm_latency_ms"] for r in results if r.get("llm_latency_ms")]
    tok = [r["tokens_out"] for r in results if r.get("tokens_out")]
    return {
        "model": model,
        "cases": len(results),
        "fields_ok": sum(r["fields_ok"] for r in results),
        "fields_total": sum(r["fields_total"] for r in results),
        "cases_exact": sum(1 for r in results if r["exact"]),
        "by_field": {k: {"ok": ok_cat[k], "total": tot_cat[k]} for k in sorted(tot_cat)},
        "json_valid_first_try": sum(1 for r in results if "error" not in r and (r.get("attempts") or 1) == 1),
        "extraction_failed": [r["id"] for r in results if "error" in r],
        "llm_latency_ms": {"p50": int(statistics.median(lat)) if lat else None, "p95": pct(lat, 0.95)},
        "tokens_out_p50": int(statistics.median(tok)) if tok else None,
        "loadavg_before": before,
        "loadavg_after": after,
        "results": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.yaml"))
    ap.add_argument("--host", default="http://ollama:11434")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    cases = load_cases(args.cases)
    out: dict[str, Any] = {
        "script_version": SCRIPT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "cases_file": str(args.cases),
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "synthetic": True,
        "models": {},
    }
    for model in args.models:
        started = time.perf_counter()
        out["models"][model] = run_model(model, cases, args.host)
        out["models"][model]["wall_s"] = round(time.perf_counter() - started, 1)
        summary = {k: v for k, v in out["models"][model].items() if k != "results"}
        print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
        try:  # libera la RAM antes del siguiente modelo
            import httpx

            httpx.post(f"{args.host}/api/generate", json={"model": model, "keep_alive": 0}, timeout=30)
        except Exception:  # noqa: BLE001
            pass
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
