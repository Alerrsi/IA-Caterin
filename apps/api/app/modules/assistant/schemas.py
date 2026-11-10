import uuid

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    quick_action: str | None = Field(None, max_length=40, description="id de una acción rápida: va directo al nivel 0")


class Source(BaseModel):
    kind: str
    label: str


class Option(BaseModel):
    label: str
    question: str


class AskOut(BaseModel):
    interaction_id: uuid.UUID | None = None
    answer: str
    level: int = Field(
        description="0 = plantilla sin LLM; 1 = el LLM redactó con el dato ya resuelto; 2 = desde documentos "
        "(fragmento citado o resumen del LLM, ver `sources`)"
    )
    intent: str | None
    status: str = Field(description="ok | no_data | ambiguous | missing_entity | unrecognized")
    sources: list[Source] = []
    options: list[Option] = Field([], description="Botones para aclarar (opciones o intenciones probables)")
    fallback_reason: str | None = None
    cache_hit: bool = False
    latency_ms: int


class QuickActionOut(BaseModel):
    id: str
    label: str
    question: str


class FeedbackIn(BaseModel):
    interaction_id: uuid.UUID
    useful: bool
