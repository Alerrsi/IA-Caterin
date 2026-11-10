"""División de un texto en frases con su contexto (para indexar y para responder sin LLM, ADR-005).

Cada frase guarda su **contexto** (título, sección y etiqueta del párrafo: "Masa: …", "Sopaipillas: …") y el
**párrafo** completo al que pertenece, para mostrarlo entero si es corto. Una tabla ("a | b | c" con encabezado,
como la deja `parsing._rows_to_chunks`) da una frase por fila: "a: x; b: y".
"""

import re
from dataclasses import dataclass

SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[¿¡\"«(A-ZÁÉÍÓÚÑ0-9])")
LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
PARAGRAPH_LABEL = re.compile(r"^([^:.;]{2,40}):\s")  # "Masa: 250 g…", "Empanadas de pino: contienen…"
END_PUNCT = (".", "?", "!", "…")
HEADING_AS_SENTENCE = 30


@dataclass(frozen=True)
class Sentence:
    text: str
    context: str
    paragraph: str


def _is_heading(line: str, is_last: bool) -> bool:
    """Título o encabezado de sección: "# …", o una línea sin punto final seguida de más texto."""
    s = line.strip()
    if s.startswith("#"):
        return True
    return not is_last and len(s) <= 120 and not s.endswith((*END_PUNCT, ";", ",")) and "|" not in s


def _lines(text: str) -> list[str]:
    lines: list[str] = []
    for ln in (x.strip() for x in text.splitlines()):
        if not ln:
            continue
        # PDF: una línea cortada a la mitad sigue en minúscula en la siguiente; se vuelven a unir.
        if lines and ln[0].islower() and not lines[-1].endswith((*END_PUNCT, ":")):
            lines[-1] = f"{lines[-1]} {ln}"
        else:
            lines.append(ln)
    return lines


def split_sentences(text: str, title: str = "", section: str = "") -> list[Sentence]:
    """`title` y `section`: los que venían del fragmento anterior del mismo documento (un fragmento del medio
    no trae el título, pero sus frases siguen siendo de ese documento y esa sección)."""
    return split_with_state(text, title, section)[0]


def split_with_state(text: str, title: str = "", section: str = "") -> tuple[list[Sentence], str, str]:
    lines = _lines(text)
    if len(lines) >= 2 and all(" | " in ln for ln in lines[:2]):
        header = [h.strip() for h in lines[0].split(" | ")]
        rows = []
        for ln in lines[1:]:
            cells = [c.strip() for c in ln.split(" | ")]
            row = "; ".join(f"{h}: {c}" for h, c in zip(header, cells, strict=False) if c)
            rows.append(Sentence(row, "", row))
        return rows, title, section
    out: list[Sentence] = []
    for n, ln in enumerate(lines):
        if _is_heading(ln, n == len(lines) - 1):
            clean = ln.lstrip("#").strip()
            if not title:
                title = clean
            else:
                section = clean
            # Un título largo también es una frase: "PIE DE LIMÓN (molde de 24 cm, 12 porciones)" responde las
            # porciones. Uno corto ("## Despacho") solo da contexto: como respuesta no dice nada.
            if len(clean) >= HEADING_AS_SENTENCE:
                out.append(Sentence(clean, title if clean != title else "", clean))
            continue
        body = LIST_PREFIX.sub("", ln)
        label = m.group(1) if (m := PARAGRAPH_LABEL.match(body)) else ""
        context = " · ".join(x for x in (title, section, label) if x)
        out.extend(Sentence(s.strip(), context, body) for s in SENTENCE_END.split(body) if s.strip())
    return out, title, section
