"""Reranker sobre los candidatos de la búsqueda híbrida (T10, ADR-003).

`eval_rag.py` con `RAG_DUMP_CANDIDATES=1` deja `candidates_<variante>.json` (10 candidatos por pregunta, en el
orden de la búsqueda híbrida). Este script los reordena con `BAAI/bge-reranker-v2-m3` (cross-encoder,
`sentence-transformers` en CPU) y compara recall@1, recall@5 y MRR antes y después, más la latencia del
reranker por pregunta según cuántos candidatos recibe (5 o 10). Además prueba si el PUNTAJE del reranker sirve
para no responder cuando la respuesta no está en los documentos (preguntas con `doc: null`): para cada umbral,
qué parte de las preguntas con respuesta conserva su fragmento correcto y cuántas sin respuesta igual reciben
fragmentos (falsos positivos). Se compara con el mismo barrido sobre la similitud de `bge-m3`.

Corre FUERA de la imagen de la API (necesita PyTorch, que la imagen no instala a propósito):

    python -m venv env && env/bin/pip install sentence-transformers==5.1.2
    env/bin/python ml/evals/rag/rerank_eval.py --candidates ml/evals/rag/candidates_bge-m3.json

Documentos y preguntas SINTÉTICOS. La latencia depende del equipo: anotar dónde se corrió.
"""

import argparse
import json
import platform
import re
import statistics
import time
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent


def plain(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip()


def is_hit(h: dict[str, Any], q: dict[str, Any]) -> bool:
    return bool(h["filename"] == q["doc"] and plain(q["key"]) in plain(h["text"]))


def rank_of(hits: list[dict[str, Any]], q: dict[str, Any]) -> int | None:
    return next((i + 1 for i, h in enumerate(hits) if is_hit(h, q)), None)


def metrics(ranks: list[int | None]) -> dict[str, float]:
    n = len(ranks)
    return {
        "recall_at_1": round(sum(r == 1 for r in ranks) / n, 3),
        "recall_at_5": round(sum(r is not None and r <= 5 for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
    }


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(p * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, default=HERE / "candidates_bge-m3.json")
    ap.add_argument("--model", default="BAAI/bge-reranker-v2-m3")
    ap.add_argument("--out", type=Path, default=HERE / "rerank_results.json")
    args = ap.parse_args()

    import torch
    from sentence_transformers import CrossEncoder

    every = json.loads(args.candidates.read_text(encoding="utf-8"))
    cases = [c for c in every if c["doc"]]
    unanswerable = [c for c in every if not c["doc"]]
    t0 = time.perf_counter()
    model = CrossEncoder(args.model, max_length=512, device="cpu")
    load_s = time.perf_counter() - t0
    model.predict([("calentamiento", "calentamiento")])

    base = [rank_of(c["hits"], c) for c in cases]
    out: dict[str, Any] = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "system": {"cpu": platform.processor() or platform.machine(), "torch_threads": torch.get_num_threads()},
        "model": args.model,
        "candidates_file": args.candidates.name,
        "questions": len(cases),
        "unanswerable": len(unanswerable),
        "load_s": round(load_s, 1),
        "note": "Documentos y preguntas SINTÉTICOS. Corpus chico (17 fragmentos): recall@5 ya está saturado.",
        "without_reranker": metrics(base),
        "with_reranker": {},
    }
    for top_n in (5, 10):
        ranks, lat, changes = [], [], []
        for c, r0 in zip(cases, base, strict=True):
            hits = c["hits"][:top_n]
            t = time.perf_counter()
            scores = model.predict([(c["q"], h["text"]) for h in hits]) if hits else []
            lat.append((time.perf_counter() - t) * 1000)
            order = sorted(range(len(hits)), key=lambda i: -float(scores[i]))
            reranked = [hits[i] for i in order] + c["hits"][top_n:]
            r1 = rank_of(reranked, c)
            ranks.append(r1)
            if r1 != r0:
                changes.append({"q": c["q"], "rank_before": r0, "rank_after": r1})
        out["with_reranker"][f"top_{top_n}"] = {
            **metrics(ranks),
            "rerank_ms": {"p50": round(statistics.median(lat)), "p95": round(pct(lat, 0.95))},
            "rank_changes": changes,
        }
        m = out["with_reranker"][f"top_{top_n}"]
        print(f"top {top_n:2}: R@1 {m['recall_at_1']}  R@5 {m['recall_at_5']}  MRR {m['mrr']}  {m['rerank_ms']} ms")
    print("sin reranker:", out["without_reranker"])

    # ¿El puntaje separa "está en los documentos" de "no está"? Sobre los 5 primeros de la búsqueda híbrida.
    def scored(c: dict[str, Any]) -> list[tuple[float, bool]]:
        hits = c["hits"][:5]
        sc = model.predict([(c["q"], h["text"]) for h in hits]) if hits else []
        return [(float(s), bool(c["doc"]) and is_hit(h, c)) for s, h in zip(sc, hits, strict=True)]

    def vector(c: dict[str, Any]) -> list[tuple[float, bool]]:
        return [(h["similarity"] if h["similarity"] is not None else 0.0, bool(c["doc"]) and is_hit(h, c))
                for h in c["hits"][:5]]

    sweeps: dict[str, list[dict[str, Any]]] = {}
    for name, fn, grid in (
        ("reranker_score", scored, [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7]),
        ("bge_m3_similarity", vector, [0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7]),
    ):
        a = [fn(c) for c in cases]
        u = [fn(c) for c in unanswerable]
        sweeps[name] = [
            {
                "threshold": t,
                "recall_at_5": round(sum(any(s >= t and ok for s, ok in x) for x in a) / len(a), 3),
                "false_positives": sum(any(s >= t for s, _ in x) for x in u),
                "unanswerable": len(u),
            }
            for t in grid
        ]
        for row in sweeps[name]:
            print(name, row)
    out["answerability_sweep"] = sweeps
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
