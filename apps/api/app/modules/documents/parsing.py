"""Lectura y fragmentación de documentos subidos (PDF, XLSX, CSV, TXT) para el nivel 2 del asistente.

Cada fragmento guarda de dónde salió (página, hoja y filas) para poder citarlo.
El contenido es DATO: nunca se interpreta como instrucción (docs/SECURITY.md, sección 3).
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

CHUNK_CHARS = 700
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
            cut = p.rfind(" ", 0, CHUNK_CHARS)
            cut = cut if cut > CHUNK_CHARS // 2 else CHUNK_CHARS
            chunks.append(Chunk(p[:cut].strip(), dict(meta)))
            p = p[max(0, cut - OVERLAP_CHARS) :].strip()
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
