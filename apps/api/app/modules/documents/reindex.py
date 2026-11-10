"""Reindexa los documentos guardados con la indexación actual (por frase, `sentence-v1`; T10).

    docker compose -f infra/docker-compose.yml exec api python -m app.modules.documents.reindex [--all]

Por defecto solo toca los documentos con fragmentos antiguos o sin vectores. Recorre pyme por pyme con una sesión
de tenant (una pyme nunca toca los documentos de otra). Requiere Ollama con `bge-m3` para los vectores; sin él,
los documentos quedan buscables por texto, como al subirlos sin Ollama.
"""

import argparse

from sqlalchemy import select

from app.core.embeddings import get_embeddings
from app.core.tenancy import open_tenant_session
from app.db.models import Document, Pyme
from app.db.session import get_sessionmaker
from app.modules.documents import service


def main() -> None:
    ap = argparse.ArgumentParser(description="Reindexa documentos subidos.")
    ap.add_argument("--all", action="store_true", help="reindexa todos, no solo los antiguos")
    args = ap.parse_args()
    emb = get_embeddings()
    with get_sessionmaker()() as s:
        pymes = list(s.scalars(select(Pyme.id)))
    done = 0
    for pyme_id in pymes:
        db = open_tenant_session(pyme_id)
        try:
            for doc_id in list(db.scalars(select(Document.id))):
                if args.all or service.needs_reindex(db, doc_id):
                    out = service.reindex(db, emb, doc_id)
                    done += 1
                    print(f"reindexado {out.id} ({out.chunks} frases, vectores: {out.has_embeddings})")
        finally:
            db.close()
    print(f"{done} documento(s) reindexado(s)")


if __name__ == "__main__":
    main()
