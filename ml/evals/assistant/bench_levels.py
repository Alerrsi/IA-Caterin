"""Latencia del asistente por nivel, de punta a punta por SSE, contra una API corriendo (T07/T10).

Mide, para cada pregunta, el primer texto visible (primer `delta`) y la respuesta completa (`done`) del lado
del cliente, más lo que registra el servidor. Para que el nivel 1 y el 2 usen el LLM, la API debe correr con
`ASSISTANT_USE_LLM=true`; para no medir la caché, con `ASSISTANT_CACHE_SIZE=0`.

    python bench_levels.py --api http://localhost:8000/api/v1 --runs 5 --out bench_levels.json

Sube un documento SINTÉTICO de políticas a la pyme de demo (si ya está, lo reutiliza) para el nivel 2.
Solo biblioteca estándar. Las preguntas son del set de demo, no frases reales de emprendedoras.
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

QUESTIONS = {
    0: ["¿Cuánta harina me queda?", "¿Qué días despacha Harinas Cautín?"],
    1: ["¿Cuánto me sale la docena de empanadas de queso?", "¿Qué me falta comprar?"],
    2: ["¿Hasta cuándo aceptan devoluciones?", "¿Con cuánta anticipación hay que anular un evento?"],
}
POLICY = """Políticas de la pyme (DOCUMENTO SINTÉTICO DE PRUEBA, no es de una pyme real)

Devoluciones: se aceptan hasta 48 horas después de la entrega, con la boleta y el producto refrigerado.

Anulaciones: un evento se puede anular sin costo hasta 72 horas antes. Después se cobra el 50 % del total.

Despacho: dentro de Temuco y Padre Las Casas va incluido; fuera de esas comunas se cotiza aparte.
"""


def call(url: str, body: bytes, headers: dict[str, str]) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return json.loads(resp.read())


def upload_policy(api: str, auth: dict[str, str]) -> None:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="politicas-sinteticas.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n{POLICY}\r\n--{boundary}--\r\n"
    ).encode()
    try:
        call(f"{api}/documents", body, {**auth, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    except urllib.error.HTTPError as exc:
        if exc.code != 409:  # 409 = ya estaba subido
            raise


def ask_sse(api: str, auth: dict[str, str], question: str) -> dict[str, Any]:
    body = json.dumps({"question": question}).encode()
    headers = {**auth, "Content-Type": "application/json", "Accept": "text/event-stream"}
    req = urllib.request.Request(f"{api}/assistant/ask", data=body, headers=headers, method="POST")  # noqa: S310
    start = time.perf_counter()
    first: float | None = None
    event = ""
    done: dict[str, Any] = {}
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        for raw in resp:
            line = raw.decode().rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                if event in ("delta", "replace") and first is None:
                    first = time.perf_counter()
                if event == "done":
                    done = json.loads(line[6:])
    end = time.perf_counter()
    return {
        "first_text_ms": round(((first or end) - start) * 1000),
        "total_ms": round((end - start) * 1000),
        "level": done.get("level"),
        "fallback_reason": done.get("fallback_reason"),
        "answer": done.get("answer", ""),
    }


def pct(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p * (len(ordered) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000/api/v1")
    ap.add_argument("--email", default="duena.aromos@demo.local")
    ap.add_argument("--password", default="caterin-demo-2026")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    login = call(
        f"{args.api}/auth/login",
        json.dumps({"email": args.email, "password": args.password}).encode(),
        {"Content-Type": "application/json"},
    )
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    upload_policy(args.api, auth)
    for qs in QUESTIONS.values():  # calentamiento: carga los modelos en Ollama
        ask_sse(args.api, auth, qs[0])

    samples = [ask_sse(args.api, auth, q) for _ in range(args.runs) for qs in QUESTIONS.values() for q in qs]
    result: dict[str, Any] = {"measured_at": time.strftime("%Y-%m-%d %H:%M"), "runs": args.runs, "levels": {}}
    for level in sorted({s["level"] for s in samples}):  # se agrupa por el nivel que REALMENTE respondió
        group = [s for s in samples if s["level"] == level]
        first = [s["first_text_ms"] for s in group]
        total = [s["total_ms"] for s in group]
        result["levels"][str(level)] = {
            "n": len(group),
            "fallbacks": sorted({s["fallback_reason"] for s in group if s["fallback_reason"]}),
            "first_text_ms": {"p50": round(statistics.median(first)), "p95": pct(first, 0.95)},
            "total_ms": {"p50": round(statistics.median(total)), "p95": pct(total, 0.95)},
            "example_answers": sorted({s["answer"] for s in group})[:4],
        }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
