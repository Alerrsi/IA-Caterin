"""Listas y filtros completos sobre los datos del negocio, en código (ADR-006).

El RAG trae pocas fichas; una lista ("¿qué hay en el inventario?", "¿qué lácteos tengo?", "¿qué recetas llevan
huevo?", "¿cuántos proveedores tengo?") tiene que ser completa y exacta. Aquí se reconoce en código que la
pregunta pide una lista de un tipo de entidad (por su nombre o por una categoría de insumos) y se filtran
TODAS sus fichas por los términos que quedan de la pregunta. Si ninguna ficha tiene esos términos ("¿qué recetas
llevan chocolate?"), no se responde con la lista sin filtrar: la pregunta sigue al RAG, que dice "no lo encontré"
si nada se parece.
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


def _kind_and_terms(db: Session, question: str) -> tuple[str, set[str], str | None] | None:
    if not set(normalize(question).split()) & LIST_CUES:
        return None
    words = stems(question)
    kinds = [k for k, ws in KIND_WORDS.items() if words & stems(ws)]
    category = None
    if kinds in ([], ["ingredient"]):  # "¿qué lácteos tengo?", "¿qué verduras hay en bodega?": una categoría
        for cat in db.scalars(select(Ingredient.category).where(Ingredient.is_active).distinct()):
            if cat and words & stems(cat):
                kinds, category = ["ingredient"], cat
                break
    if len(kinds) != 1:
        return None
    kind = kinds[0]
    terms = words - FILLER - CUE_STEMS - stems(KIND_WORDS[kind]) - (stems(category) if category else set())
    return kind, terms, category


def _shown(question: str, terms: set[str]) -> str:
    """Las palabras de la pregunta detrás de los términos ("huevo", no la raíz "huevo"/"verdu")."""
    words = [w for w in normalize(question).split() if w[:5] in terms]
    return " ".join(dict.fromkeys(words)) or " ".join(sorted(terms))


def answer(db: Session, question: str) -> ListAnswer | None:
    """La lista completa que pide la pregunta, o None si no pide una lista (sigue el RAG)."""
    found = _kind_and_terms(db, question)
    if found is None:
        return None
    kind, terms, category = found
    cards = cards_of(db, kind)
    if category is not None:  # por el campo categoría, no por texto: "verdu" no debe calzar con "Verdulería"
        ids = set(db.scalars(select(Ingredient.id).where(Ingredient.is_active, Ingredient.category == category)))
        cards = [c for c in cards if c.entity_id in ids]
    if not cards:
        return None
    matching = [c for c in cards if terms <= stems(c.text)] if terms else cards
    if not matching:
        # Ninguna ficha de ese tipo tiene esos términos: puede estar en otro tipo ("¿qué ingredientes usan las
        # empanadas?" está en la ficha de la receta) o no estar. Lo decide el RAG, con su confianza.
        return None
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
