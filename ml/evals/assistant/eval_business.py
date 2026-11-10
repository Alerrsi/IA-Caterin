"""Preguntas abiertas sobre los datos del negocio, de punta a punta (T10, ADR-006).

Cada pregunta de `business_questions.yaml` pasa por `POST /assistant/ask` con la pyme de demo. Acierta si:
- tiene `keys`: todas aparecen en la respuesta (sin tildes ni mayúsculas);
- `expect: no_data`: la respuesta no afirma nada con seguridad (estado `no_data`, o "no estoy seguro…").

    docker run --rm --network container:caterin-api-1 -v "$PWD":/repo:z -w /repo/ml/evals/assistant caterin-api \\
        python eval_business.py --api http://127.0.0.1:8000/api/v1 --out business_results.json

Con `ASSISTANT_USE_LLM=false` mide listas y RAG extractivo; con el LLM encendido, también la redacción. Datos de
la pyme de demo (SINTÉTICOS). Solo biblioteca estándar más PyYAML.
"""

import argparse
import json
import re
import statistics
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent
NOT_EXACT = "No estoy seguro de que esto responda"


def plain(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip()


def post(url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    req = urllib.request.Request(  # noqa: S310
        url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        return json.loads(resp.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--email", default="duena.aromos@demo.local")
    ap.add_argument("--password", default="caterin-demo-2026")
    ap.add_argument("--out", type=Path, default=HERE / "business_results.json")
    ap.add_argument("--questions", type=Path, default=HERE / "business_questions.yaml",
                    help="business_questions.yaml (ajuste) o business_heldout.yaml (reservado)")
    args = ap.parse_args()
    login = post(f"{args.api}/auth/login", {"email": args.email, "password": args.password}, {})
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))["questions"]
    post(f"{args.api}/assistant/ask", {"question": "¿qué insumos tengo?"}, auth)  # sincroniza fichas, carga modelos

    rows = []
    for q in questions:
        t = time.perf_counter()
        r = post(f"{args.api}/assistant/ask", {"question": q["q"]}, auth)
        ms = round((time.perf_counter() - t) * 1000)
        answer = r["answer"]
        confident = r["status"] == "ok" and not answer.startswith(NOT_EXACT)
        if q.get("expect") == "no_data":
            ok = not confident
        else:
            ok = all(plain(k) in plain(answer) for k in q["keys"])
        rows.append({"q": q["q"], "keys": q["keys"], "expect": q.get("expect"), "ok": ok, "confident": confident,
                     "level": r["level"], "intent": r["intent"], "status": r["status"],
                     "fallback_reason": r.get("fallback_reason"), "answer": answer,
                     "sources": [s["label"] for s in r["sources"]], "client_ms": ms})
        print(f"{'OK ' if ok else 'MAL'} n{r['level']} {r['intent'] or '-':16} {ms:6} ms | {q['q']}\n    {answer[:160]}",
              flush=True)

    with_keys = [r for r in rows if r["expect"] != "no_data"]
    no_data = [r for r in rows if r["expect"] == "no_data"]
    lat = [r["client_ms"] for r in rows]
    summary = {
        "with_answer": len(with_keys),
        "with_answer_ok": sum(r["ok"] for r in with_keys),
        "no_data": len(no_data),
        "no_data_ok": sum(r["ok"] for r in no_data),
        "confident_wrong": sum(r["confident"] and not r["ok"] for r in rows),
        "by_level": {str(lv): sum(r["level"] == lv for r in rows) for lv in sorted({r["level"] for r in rows})},
        "llm_fallbacks": sum(r["fallback_reason"] is not None and r["fallback_reason"] != "no_intent" for r in rows),
        "client_ms": {"p50": round(statistics.median(lat)), "max": max(lat)},
    }
    out = {"measured_at": time.strftime("%Y-%m-%d %H:%M"), "api": args.api, "questions_file": args.questions.name,
           "note": "Pyme de demo SINTÉTICA; preguntas escritas antes de implementar (business_questions.yaml).",
           "summary": summary, "cases": rows}
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
