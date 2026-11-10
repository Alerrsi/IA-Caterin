"""Lectura y fragmentación de documentos subidos (PDF, XLSX, CSV, TXT) para el nivel 2 del asistente.

Cada fragmento guarda de dónde salió (página, hoja y filas) para poder citarlo.
El contenido es DATO: nunca se interpreta como instrucción (docs/SECURITY.md, sección 3).
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.documents.sentences import split_with_state

CHUNK_CHARS = 700
PARAGRAPH_CHARS = 350  # un párrafo más largo no se guarda para mostrarlo entero: se muestra la frase
INDEX_UNIT = "sentence-v1"
OVERLAP_CHARS = 100
ROWS_PER_CHUNK = 15

MIME = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class DocumentParseError(ValueError):
    """No se pudo leer el documento."""


@dataclass
class Chunk:
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text.replace("\x00", ""))).strip()


_BOUNDARY = re.compile(r"\n|(?<=[.!?…])\s")


def _cut_point(p: str) -> int:
    """Dónde cortar un párrafo largo: en el último salto de línea o fin de frase antes del tope, para no partir
    una frase en dos fragmentos ("se hace" | "todos los lunes"). Si no hay, en el último espacio."""
    ends = [m.end() for m in _BOUNDARY.finditer(p, 0, CHUNK_CHARS) if m.end() > CHUNK_CHARS // 2]
    if ends:
        return ends[-1]
    cut = p.rfind(" ", 0, CHUNK_CHARS)
    return cut if cut > CHUNK_CHARS // 2 else CHUNK_CHARS


def _overlap_start(p: str, cut: int) -> int:
    """El solape empieza al comienzo de una frase o línea dentro de los últimos ~100 caracteres."""
    starts = [m.end() for m in _BOUNDARY.finditer(p, max(0, cut - OVERLAP_CHARS), cut) if m.end() < cut]
    return starts[0] if starts else cut


def split_text(text: str, meta: dict[str, Any]) -> list[Chunk]:
    """Fragmentos de ~700 caracteres por párrafos, con solape de ~100 si un párrafo es muy largo."""
    text = _clean(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 2 <= CHUNK_CHARS:
            current = f"{current}\n\n{p}" if current else p
            continue
        if current:
            chunks.append(Chunk(current, dict(meta)))
        while len(p) > CHUNK_CHARS:
            cut = _cut_point(p)
            chunks.append(Chunk(p[:cut].strip(), dict(meta)))
            p = p[_overlap_start(p, cut) :].strip()
        current = p
    if current:
        chunks.append(Chunk(current, dict(meta)))
    return chunks


def _rows_to_chunks(rows: list[list[str]], meta: dict[str, Any]) -> list[Chunk]:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    header, body = rows[0], rows[1:] or [rows[0]]
    out = []
    for start in range(0, len(body), ROWS_PER_CHUNK):
        part = body[start : start + ROWS_PER_CHUNK]
        lines = [" | ".join(header)] + [" | ".join(c.strip() for c in r) for r in part]
        first = start + 2
        out.append(Chunk("\n".join(lines), {**meta, "rows": f"{first}-{first + len(part) - 1}"}))
    return out


def parse(filename: str, data: bytes) -> list[Chunk]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return [
                c for i, page in enumerate(reader.pages, 1) for c in split_text(page.extract_text() or "", {"page": i})
            ]
        if ext == ".xlsx":
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            out: list[Chunk] = []
            for ws in wb.worksheets:
                rows = [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
                out += _rows_to_chunks(rows, {"sheet": ws.title})
            return out
        if ext == ".csv":
            text = _decode(data)
            dialect = csv.Sniffer().sniff(text[:2000], delimiters=";,\t") if text.strip() else csv.excel
            return _rows_to_chunks(list(csv.reader(io.StringIO(text), dialect)), {})
        if ext in (".txt", ".md"):
            return split_text(_decode(data), {})
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(type(exc).__name__) from exc
    raise DocumentParseError(f"Tipo no permitido: {ext or 'sin extensión'}")


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError("codificación desconocida")  # pragma: no cover - latin-1 decodifica todo


def to_sentences(chunks: list[Chunk]) -> list[Chunk]:
    """Una unidad indexable por frase (ADR-005, T10): la búsqueda devuelve la frase que responde y su similitud.

    `meta` conserva la página, hoja o filas del fragmento original, más `context` (título · sección · etiqueta
    del párrafo, que se agrega al texto que se vectoriza) y `paragraph` (el párrafo, para mostrarlo si es corto).
    Las frases repetidas por el solape entre fragmentos se guardan una vez.
    """
    out: list[Chunk] = []
    seen: set[str] = set()
    title = section = ""
    for chunk in chunks:
        if chunk.meta.get("page") != (out[-1].meta.get("page") if out else None):
            title = section = ""  # una página nueva de PDF puede tener su propio encabezado
        sentences, title, section = split_with_state(chunk.text, title, section)
        for s in sentences:
            if s.text in seen:
                continue
            seen.add(s.text)
            meta = {**chunk.meta, "unit": INDEX_UNIT, "context": s.context}
            if s.paragraph != s.text and len(s.paragraph) <= PARAGRAPH_CHARS:
                meta["paragraph"] = s.paragraph
            out.append(Chunk(s.text, meta))
    return out


def embedding_text(chunk: Chunk) -> str:
    """Lo que se vectoriza: el contexto ayuda a que "¿cómo van vestidos los garzones?" encuentre "Uniforme: …"
    del manual de garzones."""
    context = chunk.meta.get("context")
    return f"{context}: {chunk.text}" if context else chunk.text
