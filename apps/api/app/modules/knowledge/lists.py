"""Listas y filtros completos sobre los datos del negocio, en código (ADR-006).

El RAG trae pocas fichas; una lista ("¿qué hay en el inventario?", "¿qué lácteos tengo?", "¿qué recetas llevan
huevo?", "¿cuántos proveedores tengo?") tiene que ser completa y exacta. Aquí se reconoce en código que la
pregunta pide una lista de un tipo de entidad (por su nombre o por una categoría de insumos) y se filtran
TODAS sus fichas por los términos que quedan de la pregunta. Los que van después de "lleva", "usa", "con" o
"vende" son obligatorios: si ninguna ficha los tiene ("¿qué recetas llevan chocolate?"), no se responde con la
lista sin filtrar y la pregunta sigue al RAG, que dice "no lo encontré" si nada se parece. Los demás ("tipos de
pescado", "me quedan") filtran solo si calzan con alguna ficha.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.units import human_qty
from app.db.models import Ingredient, KnowledgeCard
from app.modules.assistant.passages import stems
from app.modules.assistant.recognizer import normalize_question as normalize
from app.modules.knowledge.cards import SOURCE
from app.modules.knowledge.service import cards_of

MAX_ITEMS = 40  # el inventario completo de una pyme chica cabe; más allá, "y N más"

KIND_WORDS = {
    "ingredient": "inventario insumo insumos ingrediente ingredientes bodega existencias materia materias",
    "recipe": "receta recetas preparacion preparaciones",
    "supplier": "proveedor proveedores proveedora proveedoras",
    "order": "pedido pedidos encargo encargos",
}
# Palabras que piden una lista (se buscan sin quitar palabras vacías: "qué", "hay" y "tengo" lo son).
LIST_CUES = frozenset(
    [
        "que",
        "cuales",
        "lista",
        "listado",
        "listame",
        "listar",
        "muestrame",
        "muestra",
        "mostrar",
        "dame",
        "todos",
        "todas",
        "cuantos",
        "cuantas",
        "existen",
        "existe",
        "hay",
        "tengo",
        "tenemos",
        "registrados",
        "registradas",
    ]
)
CUE_STEMS = frozenset(stems(" ".join(LIST_CUES)))
# Palabras que no filtran: "¿qué elementos existen actualmente dentro del inventario?" pide la lista completa.
FILLER = frozenset(
    stems(
        "elemento elementos cosa cosas item items actualmente ahora hoy dentro registrado registrada cargado cargada"
        " disponible disponibles lleva llevan usa usan usar contiene contienen incluye incluyen tiene tienen"
        " ocupa ocupan necesita necesitan mio mios mias mi mis nuestro nuestros favor porfa porfavor cuenta"
        " todas vende venden compro compra existen existe listado lista listame muestrame mostrar registrados"
    )
)
# Lo que viene después de estas palabras es un filtro OBLIGATORIO ("recetas que llevan nueces"): si no calza con
# ninguna ficha, no hay lista. Las demás palabras con contenido son opcionales ("tipos de pescado", "me quedan"):
# filtran solo si calzan con alguna ficha; si no, se ignoran (ADR-006, T10).
FILTER_CUES = frozenset(
    [
        "lleva",
        "llevan",
        "llevar",
        "usa",
        "usan",
        "usar",
        "contiene",
        "contienen",
        "incluye",
        "incluyen",
        "vende",
        "venden",
        "con",
    ]
)
NOUN = {
    "ingredient": ("insumo", "insumos"),
    "recipe": ("receta", "recetas"),
    "supplier": ("proveedor", "proveedores"),
    "order": ("pedido activo", "pedidos activos"),
}


@dataclass
class ListAnswer:
    text: str
    status: str  # siempre "ok": sin coincidencias no hay lista
    sources: list[dict[str, str]]
    entities: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _Request:
    kind: str
    category: str | None
    required: set[str]  # después de "lleva", "usa", "con", "vende"…: deben estar en la ficha
    optional: set[str]  # el resto: filtran solo si calzan con alguna ficha


def _request(db: Session, question: str) -> _Request | None:
    plain = normalize(question).split()
    if not set(plain) & LIST_CUES:
        return None
    words = stems(question)
    kinds = [k for k, ws in KIND_WORDS.items() if words & stems(ws)]
    category = None
    if kinds in ([], ["ingredient"]):  # "¿qué lácteos tengo?", "¿qué verduras hay en bodega?": una categoría
        for cat in db.scalars(select(Ingredient.category).where(Ingredient.is_active).distinct()):
            if cat and _names_category(plain, cat):
                kinds, category = ["ingredient"], cat
                break
    if len(kinds) != 1:
        return None
    kind = kinds[0]
    ignore = FILLER | CUE_STEMS | stems(KIND_WORDS[kind]) | (stems(category) if category else set())
    cue_at = next((i for i, w in enumerate(plain) if w in FILTER_CUES), None)
    required = stems(" ".join(plain[cue_at + 1 :])) - ignore if cue_at is not None else set()
    optional = words - ignore - required
    return _Request(kind, category, required, optional)


def _names_category(words: list[str], category: str) -> bool:
    """La pregunta nombra la categoría: misma palabra o su singular/plural ("carne"/"carnes", "lácteo"/"lácteos").
    Más estricto que la raíz de 5 letras, que confundía "verdulería" con "verduras"."""
    cat_words = [w for w in normalize(category).split() if len(w) > 3]
    for w in words:
        for c in cat_words:
            short, long_ = sorted((w, c), key=len)
            if len(short) >= 4 and long_.startswith(short) and len(long_) - len(short) <= 2:
                return True
    return False


def _shown(question: str, terms: set[str]) -> str:
    """Las palabras de la pregunta detrás de los términos ("huevo", no la raíz "huevo"/"verdu")."""
    words = [w for w in normalize(question).split() if w[:5] in terms]
    return " ".join(dict.fromkeys(words)) or " ".join(sorted(terms))


def answer(db: Session, question: str) -> ListAnswer | None:
    """La lista completa que pide la pregunta, o None si no pide una lista (sigue el RAG)."""
    req = _request(db, question)
    if req is None:
        return None
    cards = cards_of(db, req.kind)
    if req.category is not None:  # por el campo categoría, no por texto: "verdu" no debe calzar con "Verdulería"
        ids = set(db.scalars(select(Ingredient.id).where(Ingredient.is_active, Ingredient.category == req.category)))
        cards = [c for c in cards if c.entity_id in ids]
    if not cards:
        return None
    card_stems = {c.id: stems(c.text) for c in cards}
    kept = {t for t in req.optional if any(t in cs for cs in card_stems.values())}  # "tipos", "quedan": fuera
    terms = req.required | kept
    matching = [c for c in cards if terms <= card_stems[c.id]]
    if not matching:
        # Ninguna ficha de ese tipo tiene esos términos: puede estar en otro tipo ("¿qué ingredientes usan las
        # empanadas?" está en la ficha de la receta) o no estar ("¿qué recetas llevan nueces?"). Lo decide el RAG,
        # con su confianza; nunca se responde con la lista sin filtrar.
        return None
    kind, category = req.kind, req.category
    singular, plural = NOUN[kind]
    src = [{"kind": "knowledge", "label": SOURCE[kind]}]
    lines = _lines(db, kind, matching[:MAX_ITEMS])
    noun = singular if len(matching) == 1 else plural
    what = (f" de {category}" if category else "") + (f" con «{_shown(question, terms)}»" if terms else "")
    more = f" y {len(matching) - MAX_ITEMS} más" if len(matching) > MAX_ITEMS else ""
    text = f"Tienes {len(matching)} {noun}{what}: " + "; ".join(lines) + more + "."
    return ListAnswer(text, "ok", src, {"kind": kind, "count": len(matching), "category": category})


def _lines(db: Session, kind: str, cards: list[KnowledgeCard]) -> list[str]:
    if kind != "ingredient":
        return [c.title for c in cards]
    ings = {i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.id.in_([c.entity_id for c in cards])))}
    return [
        f"{c.title} ({human_qty(ings[c.entity_id].stock_qty, ings[c.entity_id].base_unit)})"
        if c.entity_id in ings
        else c.title
        for c in cards
    ]
