"""Lectura de planillas CSV y Excel (docs/SECURITY.md, sección 6).

- CSV: separador `;` o `,` detectado, UTF-8 (con o sin BOM) o Latin-1 (Excel en Windows).
- Excel: openpyxl en modo solo lectura, sin evaluar fórmulas ni macros (se leen los valores cacheados).
- Encabezados normalizados: minúsculas, sin tildes, espacios -> guion bajo.
"""

import csv
import io
import unicodedata
from typing import Any

from openpyxl import load_workbook

from app.core.errors import ProblemError

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000

XLSX_MAGIC = b"PK\x03\x04"


def normalize_header(raw: Any) -> str:
    text = unicodedata.normalize("NFD", str(raw or "").strip().lower()).encode("ascii", "ignore").decode()
    return "_".join(text.replace("%", " pct").replace("(", " ").replace(")", " ").split())


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ProblemError(415, "unreadable_file", "No pudimos leer el archivo")  # pragma: no cover


def _rows_from_csv(data: bytes) -> list[list[str]]:
    text = _decode(data)
    sample = text[:4096]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _rows_from_xlsx(data: bytes) -> list[list[str]]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ProblemError(415, "unreadable_file", "No pudimos leer el Excel", "Guárdalo como .xlsx o CSV.") from exc
    ws = wb.worksheets[0]
    rows = [[_cell(v) for v in row] for row in ws.iter_rows(values_only=True, max_row=MAX_ROWS + 1)]
    wb.close()
    return rows


def read_table(filename: str, data: bytes) -> list[dict[str, str]]:
    """Devuelve las filas como diccionarios con encabezados normalizados (sin filas vacías)."""
    if len(data) > MAX_BYTES:
        raise ProblemError(413, "file_too_large", "El archivo es demasiado grande", "El máximo es 5 MB.")
    if data.startswith(XLSX_MAGIC):
        rows = _rows_from_xlsx(data)
    elif filename.lower().endswith((".xlsx", ".xls")):
        raise ProblemError(415, "unsupported_media_type", "Este tipo de archivo no está permitido", "Usa .xlsx o .csv.")
    else:
        rows = _rows_from_csv(data)
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        raise ProblemError(422, "empty_file", "El archivo está vacío")
    headers = [normalize_header(h) for h in rows[0]]
    body = rows[1:]
    if len(body) > MAX_ROWS:
        raise ProblemError(413, "too_many_rows", "El archivo tiene demasiadas filas", f"El máximo es {MAX_ROWS}.")
    return [{h: (r[i] if i < len(r) else "") for i, h in enumerate(headers) if h} for r in body]


def pick(row: dict[str, str], *names: str) -> str:
    """Primer valor no vacío entre varios nombres de columna posibles."""
    for name in names:
        value = row.get(name, "").strip()
        if value:
            return value
    return ""


def csv_safe(value: str) -> str:
    """Evita inyección de fórmulas al reexportar a CSV/Excel."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value
