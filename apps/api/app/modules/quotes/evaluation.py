"""Evaluación del extractor de pedidos campo a campo (T05; la amplía T10).

Uso (con el compose levantado y el modelo descargado):
    docker compose -f infra/docker-compose.yml exec -T api \\
        python -m app.modules.quotes.evaluation < ml/evals/extractor/cases.jsonl > ml/evals/extractor/results.json

Cada caso (JSONL): {"id", "text", "guests", "date", "items": [[receta esperada | null, cantidad, unidad]]}.
Una receta esperada `null` significa que el producto NO debe asociarse solo (no existe o es ambiguo).
Las recetas son las de la pyme de demo; la fecha de referencia es fija (lunes 9-nov-2026).
"""

import json
import statistics
import sys
import time
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.llm import LLMProvider, OllamaProvider
from app.db.seed import AROMOS
from app.modules.quotes.extractor import extract_order

TODAY = date(2026, 11, 9)


def _same_qty(got: Decimal, expected: str) -> bool:
    return got == Decimal(expected)


def evaluate_case(llm: LLMProvider, case: dict[str, Any], recipes: dict[uuid.UUID, str]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        out = extract_order(llm, case["text"], recipes, TODAY)
    except ProblemError as exc:
        return {"id": case["id"], "error": exc.code, "fields_ok": 0, "fields_total": _total(case), "exact": False}
    latency = int((time.perf_counter() - started) * 1000)
    checks: list[tuple[str, bool]] = [
        ("guests", out.guests == case["guests"]),
        ("date", (out.event_date.isoformat() if out.event_date else None) == case["date"]),
    ]
    remaining = list(out.lines)
    for recipe, qty, unit in case["items"]:
        line = next((ln for ln in remaining if ln.recipe_name == recipe), None)
        if recipe is None:
            line = next((ln for ln in remaining if ln.recipe_id is None), None)
        checks.append((f"{recipe or 'sin receta'}: producto", line is not None))
        if line is not None:
            remaining.remove(line)
        if qty is not None:
            checks.append((f"{recipe or 'sin receta'}: cantidad", line is not None and _same_qty(line.qty, qty)))
        if unit is not None:
            checks.append((f"{recipe or 'sin receta'}: unidad", line is not None and line.unit.value == unit))
    checks.append(("sin productos inventados", not remaining))
    ok = sum(1 for _, passed in checks if passed)
    return {
        "id": case["id"],
        "fields_ok": ok,
        "fields_total": len(checks),
        "exact": ok == len(checks),
        "failed": [name for name, passed in checks if not passed],
        "latency_ms": latency,
        "llm_latency_ms": out.extraction.get("latency_ms"),
        "tokens_out": out.extraction.get("tokens_out"),
        "attempts": out.extraction.get("attempts"),
        "got": [
            {"name": ln.requested_name, "recipe": ln.recipe_name, "qty": str(ln.qty), "unit": ln.unit.value}
            for ln in out.lines
        ],
        "got_guests": out.guests,
        "got_date": out.event_date.isoformat() if out.event_date else None,
    }


def _total(case: dict[str, Any]) -> int:
    return 3 + sum(1 + (q is not None) + (u is not None) for _, q, u in case["items"])


def _pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def main() -> None:
    s = get_settings()
    llm = OllamaProvider(s.ollama_url, s.llm_model, max(s.llm_timeout_s, 120), s.llm_keep_alive)
    recipes = {uuid.uuid4(): r.name for r in AROMOS.recipes}
    cases = [json.loads(line) for line in sys.stdin if line.strip()]
    results = []
    for case in cases:
        result = evaluate_case(llm, case, recipes)
        detail = result.get("failed", result.get("error"))
        print(f"{case['id']}: {result['fields_ok']}/{result['fields_total']} {detail}", file=sys.stderr)
        results.append(result)
    lat = [r["llm_latency_ms"] for r in results if r.get("llm_latency_ms")]
    tokens = [r["tokens_out"] for r in results if r.get("tokens_out")]
    summary = {
        "model": llm.name,
        "date": TODAY.isoformat(),
        "cases": len(results),
        "fields_ok": sum(r["fields_ok"] for r in results),
        "fields_total": sum(r["fields_total"] for r in results),
        "cases_exact": sum(1 for r in results if r["exact"]),
        "errors": [r["id"] for r in results if "error" in r],
        "retries": sum(1 for r in results if (r.get("attempts") or 1) > 1),
        "llm_latency_ms_p50": int(statistics.median(lat)) if lat else None,
        "llm_latency_ms_p95": _pct(lat, 0.95),
        "tokens_out_p50": int(statistics.median(tokens)) if tokens else None,
    }
    print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
