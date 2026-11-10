"""Calibra cómo se elige la frase y la confianza de la respuesta extractiva del nivel 2 (T10, ADR-005).

Usa SOLO el set de ajuste (`questions.yaml`); el reservado (`questions_heldout.yaml`) se mide después con
`eval_chat.py`, sin volver a calibrar. Corre dentro de la imagen de la API contra la base `caterin_eval`:

    docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo \\
      -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_eval \\
      -e STORAGE_DIR=/tmp/evalstore caterin-api python ml/evals/rag/calibrate_passages.py

Sube los documentos SINTÉTICOS con el código real (indexación por frase), busca cada pregunta como lo hace el
asistente y, para cada combinación de peso de la cobertura y umbrales, cuenta:
- respuestas correctas mostradas (la frase o párrafo mostrado contiene `key` y es del documento esperado),
  con confianza alta o baja;
- **seguras y equivocadas** (confianza alta con una frase que no responde, o en una pregunta sin respuesta):
  es el error grave, se exige 0;
- preguntas sin respuesta en que se dice "no está".
Elige: 0 seguras equivocadas; luego más correctas mostradas; luego más correctas con confianza alta; luego más
"no está" en las preguntas sin respuesta.
"""

import json
import sys
import time
import uuid
from itertools import product
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import delete  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.embeddings import OllamaEmbeddings  # noqa: E402
from app.core.tenancy import open_tenant_session  # noqa: E402
from app.db.models import Pyme  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.modules.assistant import passages  # noqa: E402
from app.modules.assistant.service import PASSAGE_CANDIDATES  # noqa: E402
from app.modules.documents import service  # noqa: E402
from eval_rag import documents, plain  # noqa: E402

HERE = Path(__file__).parent
COVERAGE_WEIGHTS = (0.25, 0.5, 0.75, 1.0)
HIGH_SCORES = [round(0.6 + 0.05 * i, 2) for i in range(15)]
HIGH_COVERAGES = (0.0, 0.2, 0.3, 0.4, 0.5)
LOW_SCORES = [round(0.5 + 0.05 * i, 2) for i in range(12)]


def shown(c: passages.Candidate) -> str:
    return c.paragraph if len(c.paragraph) <= passages.MAX_CHARS else c.text


def collect(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    s = get_settings()
    emb = OllamaEmbeddings("http://ollama:11434", "bge-m3", "eval", 120, "30m")
    emb.embed(["calentamiento"])
    with get_sessionmaker()() as sess:
        pyme = Pyme(name=f"eval-passages {uuid.uuid4().hex[:6]}")
        sess.add(pyme)
        sess.commit()
        pyme_id = pyme.id
    db = open_tenant_session(pyme_id)
    try:
        for name, data in documents():
            service.upload(db, emb, name, data)
        rows = []
        for q in questions:
            hits = service.search(db, emb, q["q"], max(s.assistant_rag_k, PASSAGE_CANDIDATES),
                                  s.assistant_rag_min_similarity)
            cands = passages.candidates(hits)
            covs = passages.coverages(q["q"], cands)
            rows.append({
                "q": q["q"], "doc": q["doc"],
                "cands": [
                    {
                        "sim": c.similarity, "cov": cv, "rank": c.hit_index,
                        "good": bool(q["doc"]) and hits[c.hit_index].filename == q["doc"]
                        and plain(q["key"]) in plain(shown(c)),
                    }
                    for c, cv in zip(cands, covs, strict=True)
                ],
            })
        return rows
    finally:
        db.close()
        with get_sessionmaker()() as sess:
            sess.execute(delete(Pyme).where(Pyme.id == pyme_id))
            sess.commit()


def simulate(rows: list[dict[str, Any]], w: float, hs: float, hc: float, ls: float) -> dict[str, Any]:
    r = {"shown_ok": 0, "shown_ok_high": 0, "confident_wrong": 0, "unanswerable_none": 0, "unanswerable_low": 0}
    for row in rows:
        if not row["cands"]:
            r["unanswerable_none"] += row["doc"] is None
            continue
        sc = [(c["sim"] or 0.0) + w * c["cov"] for c in row["cands"]]
        i = max(range(len(sc)), key=lambda k: (sc[k], -row["cands"][k]["rank"], -k))
        c = row["cands"][i]
        conf = "high" if sc[i] >= hs and c["cov"] >= hc else "low" if sc[i] >= ls else "none"
        if row["doc"] is None:
            r["confident_wrong"] += conf == "high"
            r["unanswerable_none"] += conf == "none"
            r["unanswerable_low"] += conf == "low"
        else:
            r["shown_ok"] += c["good"] and conf != "none"
            r["shown_ok_high"] += c["good"] and conf == "high"
            r["confident_wrong"] += (not c["good"]) and conf == "high"
    return r


def main() -> None:
    questions = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    rows = collect(questions)
    grid = []
    for w, hs, hc, ls in product(COVERAGE_WEIGHTS, HIGH_SCORES, HIGH_COVERAGES, LOW_SCORES):
        if ls > hs:
            continue
        grid.append({"coverage_weight": w, "high_min_score": hs, "high_min_coverage": hc, "low_min_score": ls,
                     **simulate(rows, w, hs, hc, ls)})
    ok = [g for g in grid if g["confident_wrong"] == 0]
    ok.sort(key=lambda g: (-g["shown_ok"], -g["shown_ok_high"], -g["unanswerable_none"], g["low_min_score"]))
    current = simulate(rows, passages.COVERAGE_WEIGHT, passages.HIGH_MIN_SCORE, passages.HIGH_MIN_COVERAGE,
                       passages.LOW_MIN_SCORE)
    out = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M"),
        "set": "questions.yaml",
        "answerable": sum(q["doc"] is not None for q in questions),
        "unanswerable": sum(q["doc"] is None for q in questions),
        "candidates_per_question": PASSAGE_CANDIDATES,
        "current": current,
        "proposed": ok[0] if ok else None,
        "top": ok[:10],
        "note": "Documentos y preguntas SINTÉTICOS. Con 0 seguras equivocadas en el set de ajuste.",
        "rows": rows,
    }
    (HERE / "passages_calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("actual:", current)
    print("propuesto:", out["proposed"])
    for g in ok[1:6]:
        print("   ", g)


if __name__ == "__main__":
    main()
