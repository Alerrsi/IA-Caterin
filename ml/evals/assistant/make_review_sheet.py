"""Genera la planilla de revisión humana de la redacción (rúbrica en rubric.md). T10.

Usa el código REAL del asistente (`service.plan` + `service.drafted`) con el LLM de verdad, pero **no escribe
nada**: no llama a `finish` (que registra la interacción). Dos pasadas, porque cada una usa su base:

    # nivel 1: datos de la pyme de demo (base de desarrollo, solo lectura)
    docker run --rm --network caterin_default -v "$PWD":/repo -w /repo -e ASSISTANT_USE_LLM=true \
      -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin \
      caterin-api python ml/evals/assistant/make_review_sheet.py --level 1
    # nivel 2: documentos sintéticos de ml/evals/rag/docs en una pyme temporal de la base caterin_eval
    docker run --rm --network caterin_default -v "$PWD":/repo -w /repo -e ASSISTANT_USE_LLM=true \
      -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_eval \
      -e STORAGE_DIR=/tmp/evalstore caterin-api python ml/evals/assistant/make_review_sheet.py --level 2 --append

Salida: `review_sheet.csv` (`;`, UTF-8 con BOM, para Excel), con columnas vacías para 2 revisores.
"""

import argparse
import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from sqlalchemy import delete, select  # noqa: E402

from app.core.embeddings import OllamaEmbeddings  # noqa: E402
from app.core.llm import OllamaProvider  # noqa: E402
from app.core.tenancy import open_tenant_session  # noqa: E402
from app.db.models import Pyme  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.modules.assistant import service  # noqa: E402
from app.modules.assistant.schemas import AskIn  # noqa: E402
from app.modules.documents import service as documents  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "review_sheet.csv"
OLLAMA = "http://ollama:11434"

LEVEL1 = [
    "¿Cuánto me sale la docena de empanadas de queso?",
    "¿Cuánto cuesta hacer 50 canapés de salmón?",
    "¿A cuánto me sale producir 100 mini quiches?",
    "costo de 3 docenas de sopaipillas",
    "¿Qué pedidos tengo en los próximos 30 días?",
    "pedidos de esta semana",
    "¿Dónde está más barata la harina?",
    "¿Quién vende más barata la crema de leche?",
    "mejor precio del queso crema",
    "¿Me alcanza para el pedido del matrimonio?",
    "¿Tengo suficiente harina para el pedido del cóctel de oficina?",
    "¿Cuánto me cuestan 40 brochetas de pollo?",
]
LEVEL2 = [
    "¿Cuál es el pedido mínimo de Harinas Cautín?",
    "si el cliente anula 5 días antes, ¿cuánto le devuelvo?",
    "¿las sopaipillas llevan huevo?",
    "¿a qué temperatura tiene que estar el refri?",
    "¿cuánto se cobra la hora extra de garzón?",
    "¿con cuánta anticipación hay que pedir para 150 personas?",
    "¿se puede congelar el pie de limón?",
    "¿pueden garantizar que no hay nueces?",
    "¿cuál es el RUT de Harinas Cautín?",  # no está en los documentos: debería decirlo
]
HEADERS = [
    "id", "nivel", "pregunta", "dato_de_entrada", "respuesta_llm", "motivo_descartada", "respuesta_mostrada",
    "tokens", "rev1_correccion", "rev1_claridad", "rev1_tono", "rev1_comentario",
    "rev2_correccion", "rev2_claridad", "rev2_tono", "rev2_comentario",
]


def rows_for(db, questions: list[str], level: int, emb) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    llm = OllamaProvider(OLLAMA, "qwen3:4b", 120, "30m")
    today = datetime.now(ZoneInfo("America/Santiago")).date()
    out = []
    for q in questions:
        turn = service.plan(db, AskIn(question=q), emb, today)
        if turn.draft is None or turn.draft.level != level:
            print(f"  (omitida: no llegó al nivel {level}) {q} -> nivel {turn.base.level}, {turn.base.status}")
            continue
        res = service.Drafted()
        for _ in service.drafted(llm, turn.draft, res):
            pass
        shown = res.text if res.reason is None else turn.base.text
        out.append(
            {
                "id": uuid.uuid4().hex[:8],
                "nivel": level,
                "pregunta": q,
                "dato_de_entrada": turn.draft.facts,
                "respuesta_llm": res.text,
                "motivo_descartada": res.reason or "",
                "respuesta_mostrada": shown,
                "tokens": res.tokens_out or "",
            }
        )
        print(f"  [{res.reason or 'ok'}] {q}\n      -> {res.text}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, choices=(1, 2), required=True)
    ap.add_argument("--append", action="store_true")
    a = ap.parse_args()
    emb = OllamaEmbeddings(OLLAMA, "bge-m3", "review", 120, "30m")

    if a.level == 1:
        with get_sessionmaker()() as s:
            pyme_id = s.scalar(select(Pyme.id).where(Pyme.is_demo.is_(True), Pyme.name.like("Cocina%")))
        assert pyme_id, "No está la pyme de demo en esta base (correr el seed)"
        db = open_tenant_session(pyme_id)
        rows = rows_for(db, LEVEL1, 1, emb)
        db.rollback()  # solo lectura
        db.close()
    else:
        from eval_rag import documents as rag_docs  # ml/evals/rag: mismos documentos sintéticos

        with get_sessionmaker()() as s:
            p = Pyme(name=f"review-sheet {uuid.uuid4().hex[:6]}")
            s.add(p)
            s.commit()
            pyme_id = p.id
        db = open_tenant_session(pyme_id)
        try:
            for name, data in rag_docs():
                documents.upload(db, emb, name, data)
            rows = rows_for(db, LEVEL2, 2, emb)
        finally:
            db.close()
            with get_sessionmaker()() as s:
                s.execute(delete(Pyme).where(Pyme.id == pyme_id))
                s.commit()

    mode = "a" if a.append and OUT.exists() else "w"
    with OUT.open(mode, encoding="utf-8-sig" if mode == "w" else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, delimiter=";")
        if mode == "w":
            w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in HEADERS})
    print(f"{len(rows)} filas -> {OUT}")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent / "rag"))
    main()
