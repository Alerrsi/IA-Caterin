"""Evaluación del nivel 2 (RAG) con el código REAL de la API: parse -> upload -> search (T10).

Corre dentro de la imagen de la API, contra una base PROPIA (`caterin_eval`, nunca la de desarrollo ni la de
pruebas), con Ollama del compose:

    docker run --rm --network caterin_default -v "$PWD":/repo -w /repo \
      -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_eval \
      -e STORAGE_DIR=/tmp/evalstore caterin-api python ml/evals/rag/eval_rag.py

Cada variante sube los documentos de `docs/` a una pyme nueva (aislada por tenant) y responde
`questions.yaml`. Métricas por variante: recall@1, recall@5 y MRR (ranking completo, similitud mínima 0),
latencia de `search` p50/p95 (incluye el embedding de la pregunta) y, por cada combinación de
`k` × similitud mínima, el recall@k y los FALSOS POSITIVOS: preguntas sin respuesta en los documentos que igual
devuelven fragmentos (el asistente respondería con un fragmento que no corresponde).

Documentos y preguntas son SINTÉTICOS. El reranker no se evalúa: no está en Ollama e instalarlo exigiría
PyTorch en la imagen (ADR-003); queda pendiente.
"""

import io
import json
import re
import statistics
import sys
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from sqlalchemy import delete  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.embeddings import DisabledEmbeddings, EmbeddingProvider, OllamaEmbeddings  # noqa: E402
from app.core.tenancy import open_tenant_session  # noqa: E402
from app.db.models import Pyme  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.modules.documents import service  # noqa: E402

HERE = Path(__file__).parent
OLLAMA = "http://ollama:11434"
RANK_K = 10
K_VALUES = (3, 4, 5)
MIN_SIMS = (0.3, 0.4, 0.45, 0.5, 0.6)
QWEN_QUERY_INSTRUCTION = (
    "Instruct: Given a question from a catering business owner, retrieve the document passage that answers it\n"
    "Query: "
)


class QueryPrefixed:
    """Qwen3-Embedding recomienda una instrucción solo en la consulta: se antepone cuando embed recibe 1 texto
    de pregunta (search). Los fragmentos se suben sin prefijo."""

    def __init__(self, inner: OllamaEmbeddings, prefix: str) -> None:
        self.inner, self.prefix = inner, prefix
        self.name, self.version = inner.name, inner.version + "+instr"
        self.query_mode = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.query_mode:
            texts = [self.prefix + t for t in texts]
        return self.inner.embed(texts)


def plain(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip()


def pdf_from(source: Path) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for page in source.read_text(encoding="utf-8").split("---"):
        y = 780
        for line in page.strip().splitlines():
            for chunk in [line[i : i + 95] for i in range(0, len(line), 95)] or [""]:
                c.drawString(40, y, chunk)
                y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def documents() -> list[tuple[str, bytes]]:
    out = []
    for p in sorted((HERE / "docs").iterdir()):
        if p.name.endswith(".pdf.txt"):
            out.append((p.name.removesuffix(".txt"), pdf_from(p)))
        else:
            out.append((p.name, p.read_bytes()))
    return out


def new_pyme(label: str) -> uuid.UUID:
    with get_sessionmaker()() as s:
        p = Pyme(name=f"eval-rag {label} {uuid.uuid4().hex[:6]}")
        s.add(p)
        s.commit()
        return p.id


def is_hit(h: Any, q: dict[str, Any]) -> bool:
    return bool(h.filename == q["doc"] and plain(q["key"]) in plain(h.text))


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(p * (len(s) - 1)))]


def evaluate(label: str, emb: EmbeddingProvider, questions: list[dict[str, Any]]) -> dict[str, Any]:
    pyme_id = new_pyme(label)
    db = open_tenant_session(pyme_id)
    t0 = time.perf_counter()
    uploaded = [service.upload(db, emb, name, data) for name, data in documents()]
    index_s = time.perf_counter() - t0
    if isinstance(emb, QueryPrefixed):
        emb.query_mode = True

    answerable = [q for q in questions if q["doc"]]
    unanswerable = [q for q in questions if not q["doc"]]
    ranks: list[int | None] = []
    latencies: list[float] = []
    misses = []
    for q in answerable:
        t = time.perf_counter()
        hits = service.search(db, emb, q["q"], RANK_K, 0.0)
        latencies.append((time.perf_counter() - t) * 1000)
        rank = next((i + 1 for i, h in enumerate(hits) if is_hit(h, q)), None)
        ranks.append(rank)
        if rank != 1:
            misses.append({"q": q["q"], "rank": rank, "top": hits[0].filename if hits else None})
    for q in unanswerable:  # también cuentan para la latencia
        t = time.perf_counter()
        service.search(db, emb, q["q"], RANK_K, 0.0)
        latencies.append((time.perf_counter() - t) * 1000)

    sweep = []
    full_a = [service.search(db, emb, q["q"], RANK_K, 0.0) for q in answerable]
    full_u = [service.search(db, emb, q["q"], RANK_K, 0.0) for q in unanswerable]
    for min_sim in MIN_SIMS:
        res_a = [service.search(db, emb, q["q"], max(K_VALUES), min_sim) for q in answerable]
        res_u = [service.search(db, emb, q["q"], max(K_VALUES), min_sim) for q in unanswerable]
        for k in K_VALUES:
            found = sum(any(is_hit(h, q) for h in hits[:k]) for q, hits in zip(answerable, res_a, strict=True))
            fp = sum(bool(hits[:k]) for hits in res_u)
            text_only_fp = sum(bool(hits[:k]) and all(h.similarity is None for h in hits[:k]) for hits in res_u)
            # Alternativa (no implementada en la API): exigir similitud vectorial también a las coincidencias de
            # texto. Se simula filtrando el ranking completo (similitud mínima 0) por `similarity >= min_sim`.
            strict_a = [[h for h in hits if h.similarity is not None and h.similarity >= min_sim] for hits in full_a]
            strict_u = [[h for h in hits if h.similarity is not None and h.similarity >= min_sim] for hits in full_u]
            strict_found = sum(any(is_hit(h, q) for h in hits[:k]) for q, hits in zip(answerable, strict_a, strict=True))
            sweep.append(
                {
                    "strict_recall_at_k": round(strict_found / len(answerable), 3),
                    "strict_false_positives": sum(bool(hits[:k]) for hits in strict_u),
                    "min_similarity": min_sim,
                    "k": k,
                    "recall_at_k": round(found / len(answerable), 3),
                    "false_positives": fp,
                    "false_positives_text_only": text_only_fp,
                    "unanswerable": len(unanswerable),
                    "avg_fragments_answerable": round(statistics.mean(len(h[:k]) for h in res_a), 2),
                }
            )
    db.close()
    n = len(answerable)
    return {
        "variant": label,
        "embedding_model": emb.name,
        "documents": len(uploaded),
        "chunks": sum(d.chunks for d in uploaded),
        "with_embeddings": all(d.has_embeddings for d in uploaded),
        "index_seconds": round(index_s, 2),
        "answerable": n,
        "recall_at_1": round(sum(r == 1 for r in ranks) / n, 3),
        "recall_at_5": round(sum(r is not None and r <= 5 for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
        "search_ms": {"p50": round(statistics.median(latencies)), "p95": round(pct(latencies, 0.95))},
        "sweep": sweep,
        "misses_at_1": misses,
        "pyme_id": str(pyme_id),
    }


def main() -> None:
    questions = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    s = get_settings()
    variants: list[tuple[str, EmbeddingProvider]] = [
        ("solo_texto", DisabledEmbeddings()),
        ("bge-m3", OllamaEmbeddings(OLLAMA, "bge-m3", "eval", 120, "30m")),
        ("qwen3-embedding-0.6b", OllamaEmbeddings(OLLAMA, "qwen3-embedding:0.6b", "eval", 120, "30m")),
        (
            "qwen3-embedding-0.6b+instr",
            QueryPrefixed(OllamaEmbeddings(OLLAMA, "qwen3-embedding:0.6b", "eval", 120, "30m"), QWEN_QUERY_INSTRUCTION),
        ),
    ]
    only = sys.argv[1:]
    results = []
    for label, emb in variants:
        if only and label not in only:
            continue
        if not isinstance(emb, DisabledEmbeddings):
            emb.embed(["calentamiento"])  # carga el modelo en Ollama: no cuenta en la latencia
        r = evaluate(label, emb, questions)
        results.append(r)
        print(
            f"{label:28} R@1 {r['recall_at_1']:.2f}  R@5 {r['recall_at_5']:.2f}  MRR {r['mrr']:.2f}  "
            f"search p50/p95 {r['search_ms']['p50']}/{r['search_ms']['p95']} ms  chunks {r['chunks']}",
            flush=True,
        )
    out = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "database": s.database_url.rsplit("/", 1)[-1],
        "questions": len(questions),
        "note": "Documentos y preguntas SINTÉTICOS (ml/evals/rag). Sin reranker (no está en Ollama).",
        "results": results,
    }
    (HERE / "rag_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    # limpieza: las pymes de la corrida (CASCADE borra documentos y fragmentos)
    with get_sessionmaker()() as sess:
        sess.execute(delete(Pyme).where(Pyme.id.in_([uuid.UUID(r["pyme_id"]) for r in results])))
        sess.commit()


if __name__ == "__main__":
    main()
