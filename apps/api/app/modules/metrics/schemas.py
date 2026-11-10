import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

BaselineTask = Literal["quote", "data_lookup"]


class SurveyCreate(BaseModel):
    stars: int = Field(ge=1, le=5, description="Satisfacción de 1 a 5 estrellas")
    comment: str | None = Field(default=None, max_length=500, description="Opcional; no escribas datos de clientes")
    context: Literal["general", "quote", "assistant", "vision"] = "general"


class QuoteTimingCreate(BaseModel):
    started_at: AwareDatetime = Field(description="Cuándo se abrió la pantalla de cotizar (reloj de la PWA)")
    ended_at: AwareDatetime = Field(description="Cuándo llegó la cotización calculada (reloj de la PWA)")
    quote_id: uuid.UUID | None = None
    source: Literal["text", "form"] | None = Field(default=None, description="Cómo se ingresó el pedido")

    @model_validator(mode="after")
    def _order(self) -> "QuoteTimingCreate":
        if self.ended_at < self.started_at:
            raise ValueError("El fin no puede ser anterior al inicio")
        return self


class ManualBaselineCreate(BaseModel):
    task: BaselineTask = Field(description="quote: cotización a mano; data_lookup: buscar un dato a mano")
    seconds: float = Field(gt=0, le=24 * 3600, description="Tiempo cronometrado, en segundos")
    reference: str = Field(
        min_length=2,
        max_length=120,
        description='Qué se midió, sin datos personales (p. ej. "pedido de referencia P1" o "stock de harina")',
    )
    repetition: int = Field(default=1, ge=1, le=50, description="Número de repetición del mismo caso")
    measured_on: date = Field(description="Día en que se cronometró")
    tool: str | None = Field(default=None, max_length=60, description='Herramienta usada, p. ej. "Excel" o "cuaderno"')
    notes: str | None = Field(default=None, max_length=500)


class MetricEventOut(BaseModel):
    id: uuid.UUID
    kind: str
    value_num: float | None
    created_at: datetime


# --------------------------------------------------------------------------- resumen


class Period(BaseModel):
    date_from: date | None = Field(description="Primer día incluido (America/Santiago); null = desde el inicio")
    date_to: date = Field(description="Último día incluido (America/Santiago)")
    timezone: str = "America/Santiago"


class Stat(BaseModel):
    n: int
    value: float | None = Field(description="null si no hay mediciones")
    unit: str
    low_n: bool = Field(description="true si n es menor que el umbral (estudio piloto)")


class Satisfaction(BaseModel):
    n: int
    mean_stars: float | None
    distribution: dict[str, int] = Field(description='Cantidad de respuestas por estrella, "1" a "5"')
    low_n: bool


class BaselineRange(BaseModel):
    first_measured_on: date | None
    last_measured_on: date | None


class QuoteTime(BaseModel):
    caterin_median: Stat = Field(description="Mediana medida por la PWA en el periodo")
    manual_median: Stat = Field(description="Mediana de la cotización manual de referencia (todas las mediciones)")
    manual_range: BaselineRange


class DataLookup(BaseModel):
    assistant_median: Stat = Field(description="Mediana de latencia total del asistente en el periodo")
    manual_median: Stat = Field(description="Mediana de buscar el dato a mano (todas las mediciones)")
    manual_range: BaselineRange


class LevelLatency(BaseModel):
    level: int
    n: int
    p50_ms: float | None
    p95_ms: float | None
    low_n: bool


class Share(BaseModel):
    n: int = Field(description="Consultas que cumplen la condición")
    total: int
    pct: float | None
    low_n: bool


class Assistant(BaseModel):
    total: int
    levels: list[LevelLatency]
    without_llm: Share = Field(description="Resueltas en nivel 0 (no se llamó al LLM)")
    degraded: Share = Field(description="Con motivo de degradación (timeout, LLM caído, cifras que no cuadran…)")


class MetricsSummary(BaseModel):
    period: Period
    low_n_threshold: int
    satisfaction: Satisfaction
    quote_time: QuoteTime
    data_lookup: DataLookup
    assistant: Assistant
    warnings: list[str]
