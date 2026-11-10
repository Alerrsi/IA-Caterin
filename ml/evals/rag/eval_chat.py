"""El chat sobre documentos de punta a punta, como lo ve la usuaria (T10).

Registra una pyme de prueba nueva (aislada, sin datos de inventario), le sube los documentos SINTÉTICOS de
`docs/` y hace cada pregunta de `questions.yaml` por `POST /assistant/ask`. A diferencia de `eval_rag.py`, que
mide la búsqueda, aquí se mide la RESPUESTA:

- pregunta con respuesta (`doc`): acierta si el texto mostrado contiene `key` (sin tildes ni mayúsculas) y
  cita el documento correcto;
- pregunta sin respuesta (`doc: null`): acierta si NO responde con seguridad desde un fragmento.

Cada respuesta se clasifica en `confident` (cita un fragmento como respuesta), `tentative` ("no estoy seguro de
que esto responda tu pregunta; lo más parecido…") o `none` (no está en sus documentos, o respondió otra cosa). Lo grave es
`confident` equivocado: la usuaria recibe un dato que no responde su pregunta.

También registra a qué nivel e intención fue cada pregunta: una pregunta de documentos que se va a una intención
del nivel 0 (p. ej. a "proveedores") es un error del enrutador, no de la búsqueda.

    docker run --rm --network container:caterin-api-1 -v "$PWD":/repo:z -w /repo/ml/evals/rag caterin-api \
        python eval_chat.py --questions questions_heldout.yaml --out chat_results_heldout.json

Con `ASSISTANT_USE_LLM=false` (por defecto) mide el nivel 2 extractivo; con el LLM encendido, la redacción
(más lento). Solo biblioteca estándar, más PyYAML.
"""

import argparse
import json
import re
import statistics
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).parent
NOT_EXACT = "No estoy seguro de que esto responda"  # prefijo de la respuesta tentativa (assistant/service.py)


def plain(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip()


def call(url: str, body: bytes, headers: dict[str, str]) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
        return json.loads(resp.read())


def upload(api: str, auth: dict[str, str], name: str, data: bytes) -> None:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    call(f"{api}/documents", body, {**auth, "Content-Type": f"multipart/form-data; boundary={boundary}"})


def documents() -> list[tuple[str, bytes]]:
    out = []
    for p in sorted((HERE / "docs").iterdir()):
        if p.name.endswith(".pdf.txt"):
            from eval_rag import pdf_from  # noqa: PLC0415 - mismo PDF que eval_rag (necesita reportlab)

            out.append((p.name.removesuffix(".txt"), pdf_from(p)))
        else:
            out.append((p.name, p.read_bytes()))
    return out


def ask(api: str, auth: dict[str, str], question: str) -> dict[str, Any]:
    t = time.perf_counter()
    r = call(f"{api}/assistant/ask", json.dumps({"question": question}).encode(),
             {**auth, "Content-Type": "application/json"})
    r["client_ms"] = round((time.perf_counter() - t) * 1000)
    return r


def pct(values: list[int], p: float) -> int:
    s = sorted(values)
    return s[min(len(s) - 1, round(p * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--out", type=Path, default=HERE / "chat_results.json")
    ap.add_argument("--questions", type=Path, default=HERE / "questions.yaml",
                    help="questions.yaml (el de eval_rag) o questions_heldout.yaml (reservado)")
    args = ap.parse_args()

    email = f"eval-chat-{uuid.uuid4().hex[:8]}@demo.local"
    reg = call(f"{args.api}/auth/register", json.dumps({
        "pyme_name": "Eval chat documentos (SINTÉTICA)", "full_name": "Evaluación T10",
        "email": email, "password": "eval-chat-2026-x",
    }).encode(), {"Content-Type": "application/json"})
    auth = {"Authorization": f"Bearer {reg['access_token']}"}
    for name, data in documents():
        upload(args.api, auth, name, data)
    ask(args.api, auth, "calentamiento")

    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in questions:
        r = ask(args.api, auth, q["q"])
        cited = [s["label"] for s in r.get("sources", []) if s.get("kind") == "document"]
        doc_answer = r["level"] == 2 and r["status"] == "ok"
        kind = ("tentative" if r["answer"].startswith(NOT_EXACT) else "confident") if doc_answer else "none"
        if q["doc"]:
            ok = plain(q["key"]) in plain(r["answer"]) and any(q["doc"] in c for c in cited)
        else:
            ok = kind != "confident"
        rows.append({
            "q": q["q"], "doc": q["doc"], "key": q.get("key"), "ok": ok, "kind": kind, "level": r["level"],
            "intent": r["intent"], "status": r["status"], "fallback_reason": r.get("fallback_reason"),
            "cited": cited, "answer": r["answer"], "latency_ms": r["latency_ms"], "client_ms": r["client_ms"],
        })
        print(f"{'OK ' if ok else 'MAL'} {kind:9} n{r['level']} {r['intent'] or '-':16} {q['q']}", flush=True)

    ans = [r for r in rows if r["doc"]]
    una = [r for r in rows if not r["doc"]]
    lat = [r["client_ms"] for r in rows]
    summary = {
        "answerable": len(ans),
        "answerable_ok": sum(r["ok"] for r in ans),
        "answerable_ok_confident": sum(r["ok"] and r["kind"] == "confident" for r in ans),
        "answerable_ok_tentative": sum(r["ok"] and r["kind"] == "tentative" for r in ans),
        "answerable_wrong_confident": sum(not r["ok"] and r["kind"] == "confident" for r in ans),
        "answerable_wrong_tentative": sum(not r["ok"] and r["kind"] == "tentative" for r in ans),
        "answerable_no_answer": sum(r["kind"] == "none" for r in ans),
        "answerable_routed_to_intent": sum(r["intent"] is not None for r in ans),
        "unanswerable": len(una),
        "unanswerable_ok": sum(r["ok"] for r in una),
        "unanswerable_said_not_found": sum(r["kind"] == "none" for r in una),
        "unanswerable_tentative": sum(r["kind"] == "tentative" for r in una),
        "unanswerable_wrong_confident": sum(r["kind"] == "confident" for r in una),
        "client_ms": {"p50": round(statistics.median(lat)), "p95": pct(lat, 0.95)},
    }
    out = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "api": args.api,
        "questions_file": args.questions.name,
        "note": "Documentos y preguntas SINTÉTICOS; pyme de prueba nueva, sin inventario ni pedidos.",
        "summary": summary,
        "cases": rows,
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
