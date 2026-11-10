"""Evaluación de punta a punta del asistente con el set dorado y el reservado (T10).

Cada pregunta de `golden.yaml` y `heldout.yaml` pasa por `POST /assistant/ask` (SSE), igual que desde la app.
Para medir los niveles 1 y 2 con el LLM, la API debe correr con `ASSISTANT_USE_LLM=true` y sin caché
(`ASSISTANT_CACHE_SIZE=0`). Mide por caso: intención y nivel que respondieron, estado, si el texto del LLM se
descartó y por qué (`figures_mismatch` = el LLM escribió una cifra que no estaba en el dato: **alucinación
atajada**), primer texto y respuesta completa. Por nivel: n, latencia p50/p95 y tasa de descarte.

    python eval_assistant.py --api http://127.0.0.1:8002/api/v1 --out eval_assistant.json

Los tokens generados no van en la respuesta de la API: se leen de `assistant_interaction` por `interaction_id`
(`--tokens-from` con un CSV `id,tokens_out` sacado con psql; ver ml/evals/REPORT.md).
Solo biblioteca estándar. Frases SINTÉTICAS escritas por el equipo; datos de la pyme de demo.
"""

import argparse
import csv
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent


def load_cases() -> list[dict[str, Any]]:
    import yaml  # disponible en la imagen de la API

    out = []
    for name in ("golden.yaml", "heldout.yaml"):
        for c in yaml.safe_load((HERE / name).read_text(encoding="utf-8"))["cases"]:
            out.append({"set": name.removesuffix(".yaml"), "q": c["q"], "expected": c["intent"]})
    return out


def post(url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    req = urllib.request.Request(  # noqa: S310
        url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
        return json.loads(resp.read())


def ask(api: str, auth: dict[str, str], question: str) -> dict[str, Any]:
    headers = {**auth, "Content-Type": "application/json", "Accept": "text/event-stream"}
    body = json.dumps({"question": question}).encode()
    req = urllib.request.Request(f"{api}/assistant/ask", data=body, headers=headers, method="POST")  # noqa: S310
    start = time.perf_counter()
    first = None
    event, drafted, replaced, done = "", "", False, {}
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
        for raw in resp:
            line = raw.decode().rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if event in ("delta", "replace") and first is None:
                    first = time.perf_counter()
                if event == "delta":
                    drafted += data.get("text", "")
                elif event == "replace":
                    replaced = True
                elif event == "done":
                    done = data
    end = time.perf_counter()
    return {
        "first_text_ms": round(((first or end) - start) * 1000),
        "total_ms": round((end - start) * 1000),
        "interaction_id": done.get("interaction_id"),
        "intent": done.get("intent"),
        "level": done.get("level"),
        "status": done.get("status"),
        "fallback_reason": done.get("fallback_reason"),
        "replaced": replaced,
        "answer": done.get("answer", ""),
        "discarded_draft": drafted if replaced else None,
    }


def pct(values: list[int], p: float) -> int:
    s = sorted(values)
    return s[min(len(s) - 1, round(p * (len(s) - 1)))]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for level in sorted({r["level"] for r in rows}, key=lambda x: (x is None, x)):
        g = [r for r in rows if r["level"] == level]
        reasons: dict[str, int] = {}
        for r in g:
            if r["fallback_reason"]:
                reasons[r["fallback_reason"]] = reasons.get(r["fallback_reason"], 0) + 1
        tokens = [r["tokens_out"] for r in g if r.get("tokens_out")]
        out[str(level)] = {
            "n": len(g),
            "first_text_ms": {"p50": round(statistics.median(x["first_text_ms"] for x in g)),
                              "p95": pct([x["first_text_ms"] for x in g], 0.95)},
            "total_ms": {"p50": round(statistics.median(x["total_ms"] for x in g)),
                         "p95": pct([x["total_ms"] for x in g], 0.95)},
            "fallback_reasons": reasons,
            "replaced": sum(r["replaced"] for r in g),
            "tokens_out_p50": statistics.median(tokens) if tokens else None,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--email", default="duena.aromos@demo.local")
    ap.add_argument("--password", default="caterin-demo-2026")
    ap.add_argument("--out", type=Path, default=HERE / "eval_assistant.json")
    ap.add_argument("--tokens-from", type=Path, help="CSV id,tokens_out: solo vuelve a resumir --out con los tokens")
    args = ap.parse_args()

    if args.tokens_from:
        res = json.loads(args.out.read_text(encoding="utf-8"))
        with args.tokens_from.open() as f:
            tok = {row["id"]: int(row["tokens_out"]) for row in csv.DictReader(f) if row["tokens_out"]}
        for r in res["cases"]:
            r["tokens_out"] = tok.get(r["interaction_id"] or "")
        res["by_level"] = summarize(res["cases"])
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(res["by_level"], ensure_ascii=False, indent=2))
        return

    login = post(f"{args.api}/auth/login", {"email": args.email, "password": args.password}, {})
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    ask(args.api, auth, "¿Cuánto me sale la docena de empanadas de queso?")  # calentamiento (carga el LLM)

    rows = []
    for c in load_cases():
        r = {**c, **ask(args.api, auth, c["q"])}
        r["intent_ok"] = r["intent"] == c["expected"]
        rows.append(r)
        print(f"{r['level']} {r['intent_ok']!s:5} {r['total_ms']:6} ms {r['fallback_reason'] or '':16} {c['q']}",
              flush=True)

    by_set = {}
    for s in ("golden", "heldout"):
        g = [r for r in rows if r["set"] == s]
        by_set[s] = {"n": len(g), "intent_ok": sum(r["intent_ok"] for r in g),
                     "wrong_intent": sum(r["intent"] is not None and not r["intent_ok"] for r in g)}
    drafted = [r for r in rows if r["level"] in (1, 2) or r["fallback_reason"] in ("figures_mismatch", "llm_timeout")]
    res = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "api": args.api,
        "note": "Frases SINTÉTICAS (golden + heldout), pyme de demo. Equipo y carga: ver ml/evals/REPORT.md.",
        "by_set": by_set,
        "figures_mismatch": sum(r["fallback_reason"] == "figures_mismatch" for r in rows),
        "llm_drafts": len(drafted),
        "by_level": summarize(rows),
        "cases": rows,
    }
    args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("by_set", "figures_mismatch", "llm_drafts", "by_level")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
