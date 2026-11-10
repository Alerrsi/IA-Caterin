"""Registro y resumen de métricas de éxito (T09).

- Todas las consultas pasan por la sesión de tenant (`core/tenancy.py`), que filtra por `pyme_id`.
- El resumen se calcula con funciones puras (`stats.py`) sobre los valores crudos, con `Decimal`.
- Las mediciones manuales de referencia no se recortan por el periodo: son la línea base "antes".
"""

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.orm import Session

from app.core.errors import ProblemError
from app.core.tenancy import CurrentUser
from app.db.enums import MetricKind
from app.db.models import AssistantInteraction, MetricEvent, Pyme
from app.modules.metrics import stats
from app.modules.metrics.schemas import (
    Assistant,
    BaselineRange,
    BaselineTask,
    DataLookup,
    LevelLatency,
    ManualBaselineCreate,
    MetricsSummary,
    Period,
    QuoteTime,
    QuoteTimingCreate,
    Satisfaction,
    Share,
    Stat,
    SurveyCreate,
)
from app.modules.quotes.service import MAX_TIMING_S, get_quote

TZ = ZoneInfo("America/Santiago")
ASSISTANT_LEVELS = (0, 1, 2, 3)


# --------------------------------------------------------------------------- registro


def record_survey(db: Session, user: CurrentUser, data: SurveyCreate) -> MetricEvent:
    payload: dict[str, Any] = {"context": data.context}
    if data.comment and data.comment.strip():
        payload["comment"] = data.comment.strip()
    event = MetricEvent(user_id=user.id, kind=MetricKind.SURVEY, value_num=Decimal(data.stars), payload=payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _timing_for_quote(db: Session, quote_id: uuid.UUID) -> MetricEvent | None:
    return db.scalar(
        select(MetricEvent).where(
            MetricEvent.kind == MetricKind.QUOTE_TIMING,
            MetricEvent.payload["quote_id"].astext == str(quote_id),
        )
    )


def record_quote_timing(db: Session, user: CurrentUser, data: QuoteTimingCreate) -> tuple[MetricEvent, bool]:
    """Guarda el tiempo de una cotización. Devuelve (evento, creado). Idempotente por `quote_id`."""
    seconds = (data.ended_at - data.started_at).total_seconds()
    if seconds > MAX_TIMING_S:
        raise ProblemError(
            422, "timing_out_of_range", "El tiempo no es válido", "Una cotización no puede durar más de 24 horas."
        )
    payload: dict[str, Any] = {
        "started_at": data.started_at.astimezone(UTC).isoformat(),
        "ended_at": data.ended_at.astimezone(UTC).isoformat(),
        "measured_by": "pwa",
    }
    if data.source:
        payload["source"] = data.source
    if data.quote_id is not None:
        quote = get_quote(db, data.quote_id)  # 404 si es de otra pyme o no existe
        existing = _timing_for_quote(db, quote.id)
        if existing is not None:
            return existing, False
        payload["quote_id"] = str(quote.id)
        payload["order_id"] = str(quote.order_id)
    event = MetricEvent(
        user_id=user.id,
        kind=MetricKind.QUOTE_TIMING,
        value_num=Decimal(str(round(seconds, 1))),
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event, True


def record_manual_baseline(db: Session, user: CurrentUser, data: ManualBaselineCreate) -> MetricEvent:
    payload: dict[str, Any] = {
        "task": data.task,
        "reference": data.reference.strip(),
        "repetition": data.repetition,
        "measured_on": data.measured_on.isoformat(),
    }
    if data.tool:
        payload["tool"] = data.tool.strip()
    if data.notes and data.notes.strip():
        payload["notes"] = data.notes.strip()
    event = MetricEvent(
        user_id=user.id,
        kind=MetricKind.MANUAL_BASELINE,
        value_num=Decimal(str(round(data.seconds, 1))),
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# --------------------------------------------------------------------------- resumen


@dataclass(frozen=True)
class Window:
    """Periodo del resumen en días de Chile, convertido a un rango UTC semiabierto [start, end)."""

    date_from: date | None
    date_to: date

    @classmethod
    def build(cls, date_from: date | None, date_to: date | None) -> "Window":
        to = date_to or datetime.now(TZ).date()
        if date_from is not None and date_from > to:
            raise ProblemError(
                422, "bad_period", "El periodo no es válido", "La fecha inicial es posterior a la final."
            )
        return cls(date_from, to)

    @property
    def start(self) -> datetime | None:
        return datetime.combine(self.date_from, time.min, TZ) if self.date_from else None

    @property
    def end(self) -> datetime:
        return datetime.combine(self.date_to + timedelta(days=1), time.min, TZ)

    def clause(self, column: Any) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = [column < self.end]
        if self.start is not None:
            clauses.append(column >= self.start)
        return clauses


@dataclass(frozen=True)
class Scope:
    """Para el informe del equipo (varias pymes). En la API se usa la sesión de tenant y queda vacío."""

    exclude_demo: bool = False

    def clause(self, column: Any) -> list[ColumnElement[bool]]:
        if not self.exclude_demo:
            return []
        return [column.in_(select(Pyme.id).where(Pyme.is_demo.is_(False)))]


def _metric_values(db: Session, kind: MetricKind, window: Window | None, scope: Scope) -> list[Decimal]:
    stmt = select(MetricEvent.value_num).where(
        MetricEvent.kind == kind, MetricEvent.value_num.is_not(None), *scope.clause(MetricEvent.pyme_id)
    )
    if window is not None:
        stmt = stmt.where(*window.clause(MetricEvent.created_at))
    return [v for v in db.scalars(stmt) if v is not None]


def _baseline(db: Session, task: BaselineTask, scope: Scope) -> tuple[list[Decimal], BaselineRange]:
    measured_on = MetricEvent.payload["measured_on"].astext
    stmt: Select[Any] = select(MetricEvent.value_num, measured_on).where(
        MetricEvent.kind == MetricKind.MANUAL_BASELINE,
        MetricEvent.payload["task"].astext == task,
        *scope.clause(MetricEvent.pyme_id),
    )
    rows = db.execute(stmt).all()
    days = sorted(date.fromisoformat(r[1]) for r in rows if r[1])
    return [r[0] for r in rows], BaselineRange(
        first_measured_on=days[0] if days else None, last_measured_on=days[-1] if days else None
    )


def _stat(value: Decimal | None, n: int, unit: str, places: int = 1) -> Stat:
    return Stat(n=n, value=stats.rounded(value, places), unit=unit, low_n=stats.is_low_n(n))


def _share(part: int, total: int) -> Share:
    return Share(n=part, total=total, pct=stats.rounded(stats.share_pct(part, total), 1), low_n=stats.is_low_n(total))


def _satisfaction(db: Session, window: Window, scope: Scope) -> Satisfaction:
    stars = _metric_values(db, MetricKind.SURVEY, window, scope)
    dist = {str(s): 0 for s in range(1, 6)}
    for s in stars:
        dist[str(int(s))] = dist.get(str(int(s)), 0) + 1
    return Satisfaction(
        n=len(stars),
        mean_stars=stats.rounded(stats.mean(stars), 2),
        distribution=dist,
        low_n=stats.is_low_n(len(stars)),
    )


AssistantRow = tuple[int, int, str | None, str | None]  # nivel, latencia, motivo de degradación, modelo LLM


def _assistant_rows(db: Session, window: Window, scope: Scope) -> list[AssistantRow]:
    stmt = select(
        AssistantInteraction.level,
        AssistantInteraction.latency_ms,
        AssistantInteraction.fallback_reason,
        AssistantInteraction.llm_model,
    ).where(*window.clause(AssistantInteraction.created_at), *scope.clause(AssistantInteraction.pyme_id))
    return [(r[0], r[1], r[2], r[3]) for r in db.execute(stmt).all()]


def _assistant(rows: list[AssistantRow]) -> Assistant:
    levels = []
    for level in ASSISTANT_LEVELS:
        lat = [r[1] for r in rows if r[0] == level]
        if not lat and level == 3:
            continue  # el nivel 3 está apagado por defecto: no se muestra vacío
        levels.append(
            LevelLatency(
                level=level,
                n=len(lat),
                p50_ms=stats.rounded(stats.percentile(lat, 0.5), 0),
                p95_ms=stats.rounded(stats.percentile(lat, 0.95), 0),
                low_n=stats.is_low_n(len(lat)),
            )
        )
    total = len(rows)
    return Assistant(
        total=total,
        levels=levels,
        without_llm=_share(sum(1 for r in rows if r[3] is None), total),  # no se llamó al LLM
        degraded=_share(sum(1 for r in rows if r[2]), total),
    )


def _warnings(summary: MetricsSummary) -> list[str]:
    out: list[str] = []
    low = summary.low_n_threshold
    sat_n = summary.satisfaction.n
    if sat_n == 0:
        out.append("Satisfacción: todavía no hay respuestas a la encuesta.")
    elif summary.satisfaction.low_n:
        out.append(f"Satisfacción: solo {sat_n} respuestas (menos de {low}).")
    qt = summary.quote_time
    if qt.caterin_median.n == 0:
        out.append("Tiempo de cotización con Cáterin: todavía no hay cotizaciones medidas en el periodo.")
    elif qt.caterin_median.low_n:
        out.append(f"Tiempo de cotización con Cáterin: solo {qt.caterin_median.n} mediciones (menos de {low}).")
    if qt.manual_median.n == 0:
        out.append("Falta la medición manual de referencia: no se puede comparar el antes y el después.")
    elif qt.manual_median.low_n:
        out.append(f"Cotización manual de referencia: solo {qt.manual_median.n} mediciones (menos de {low}).")
    if summary.data_lookup.manual_median.n == 0:
        out.append("Falta medir cuánto se tarda en buscar un dato a mano.")
    if summary.assistant.total == 0:
        out.append("El asistente todavía no tiene consultas registradas en el periodo.")
    elif summary.assistant.without_llm.low_n:
        out.append(f"Asistente: solo {summary.assistant.total} consultas (menos de {low}).")
    return out


def build_summary(db: Session, window: Window, scope: Scope | None = None) -> MetricsSummary:
    scope = scope or Scope()
    quote_values = _metric_values(db, MetricKind.QUOTE_TIMING, window, scope)
    manual_quote, manual_quote_range = _baseline(db, "quote", scope)
    manual_lookup, manual_lookup_range = _baseline(db, "data_lookup", scope)
    rows = _assistant_rows(db, window, scope)
    assistant_s = [Decimal(r[1]) / 1000 for r in rows]
    summary = MetricsSummary(
        period=Period(date_from=window.date_from, date_to=window.date_to),
        low_n_threshold=stats.LOW_N_THRESHOLD,
        satisfaction=_satisfaction(db, window, scope),
        quote_time=QuoteTime(
            caterin_median=_stat(stats.median(quote_values), len(quote_values), "s"),
            manual_median=_stat(stats.median(manual_quote), len(manual_quote), "s"),
            manual_range=manual_quote_range,
        ),
        data_lookup=DataLookup(
            assistant_median=_stat(stats.median(assistant_s), len(assistant_s), "s", places=2),
            manual_median=_stat(stats.median(manual_lookup), len(manual_lookup), "s"),
            manual_range=manual_lookup_range,
        ),
        assistant=_assistant(rows),
        warnings=[],
    )
    summary.warnings = _warnings(summary)
    return summary


# --------------------------------------------------------------------------- CSV


CSV_HEADER = ["seccion", "metrica", "segmento", "n", "valor", "unidad", "n_bajo", "desde", "hasta"]


def _fmt(value: float | None) -> str:
    """Coma decimal: el CSV se abre directo en Excel configurado en español de Chile."""
    return "" if value is None else f"{value:g}".replace(".", ",")


def summary_csv(summary: MetricsSummary) -> str:
    p = summary.period
    since = p.date_from.isoformat() if p.date_from else ""
    until = p.date_to.isoformat()
    qt, dl, a = summary.quote_time, summary.data_lookup, summary.assistant
    rows: list[list[str]] = [
        [
            "satisfaccion",
            "promedio_estrellas",
            "",
            str(summary.satisfaction.n),
            _fmt(summary.satisfaction.mean_stars),
            "estrellas",
            _yes(summary.satisfaction.low_n),
            since,
            until,
        ],
    ]
    for star, count in summary.satisfaction.distribution.items():
        rows.append(
            [
                "satisfaccion",
                "respuestas",
                f"{star}_estrellas",
                str(count),
                str(count),
                "respuestas",
                _yes(summary.satisfaction.low_n),
                since,
                until,
            ]
        )
    rows += [
        ["tiempo_cotizacion", "mediana", "con_caterin", *_stat_cells(qt.caterin_median), since, until],
        [
            "tiempo_cotizacion",
            "mediana",
            "manual",
            *_stat_cells(qt.manual_median),
            _day(qt.manual_range.first_measured_on),
            _day(qt.manual_range.last_measured_on),
        ],
        ["buscar_dato", "mediana", "asistente", *_stat_cells(dl.assistant_median), since, until],
        [
            "buscar_dato",
            "mediana",
            "manual",
            *_stat_cells(dl.manual_median),
            _day(dl.manual_range.first_measured_on),
            _day(dl.manual_range.last_measured_on),
        ],
    ]
    for lv in a.levels:
        rows.append(
            [
                "asistente",
                "latencia_p50",
                f"nivel_{lv.level}",
                str(lv.n),
                _fmt(lv.p50_ms),
                "ms",
                _yes(lv.low_n),
                since,
                until,
            ]
        )
        rows.append(
            [
                "asistente",
                "latencia_p95",
                f"nivel_{lv.level}",
                str(lv.n),
                _fmt(lv.p95_ms),
                "ms",
                _yes(lv.low_n),
                since,
                until,
            ]
        )
    rows += [
        [
            "asistente",
            "pct_sin_llm",
            "",
            str(a.without_llm.total),
            _fmt(a.without_llm.pct),
            "%",
            _yes(a.without_llm.low_n),
            since,
            until,
        ],
        [
            "asistente",
            "pct_degradadas",
            "",
            str(a.degraded.total),
            _fmt(a.degraded.pct),
            "%",
            _yes(a.degraded.low_n),
            since,
            until,
        ],
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    writer.writerows(rows)
    return "﻿" + buf.getvalue()  # BOM: Excel reconoce los tildes


def _day(d: date | None) -> str:
    return d.isoformat() if d else ""


def _yes(flag: bool) -> str:
    return "si" if flag else "no"


def _stat_cells(s: Stat) -> list[str]:
    return [str(s.n), _fmt(s.value), s.unit, _yes(s.low_n)]
