"""Métricas de éxito (T09): encuesta, tiempo de cotización, línea base manual y panel de la dueña."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
from app.db.models import MetricEvent
from app.modules.metrics import service
from app.modules.metrics.schemas import (
    ManualBaselineCreate,
    MetricEventOut,
    MetricsSummary,
    QuoteTimingCreate,
    SurveyCreate,
)

router = APIRouter(prefix="/metrics", tags=["métricas"])

DateFrom = Annotated[date | None, Query(alias="from", description="Primer día incluido (America/Santiago)")]
DateTo = Annotated[date | None, Query(alias="to", description="Último día incluido; por defecto, hoy")]


def _out(event: MetricEvent) -> MetricEventOut:
    return MetricEventOut(
        id=event.id,
        kind=event.kind.value,
        value_num=float(event.value_num) if event.value_num is not None else None,
        created_at=event.created_at,
    )


@router.post("/survey", response_model=MetricEventOut, status_code=status.HTTP_201_CREATED)
def post_survey(data: SurveyCreate, user: CurrentUserDep, db: TenantDB) -> MetricEventOut:
    """Encuesta de satisfacción de 1 a 5 estrellas, con comentario opcional."""
    return _out(service.record_survey(db, user, data))


@router.post(
    "/quote-timing",
    response_model=MetricEventOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": MetricEventOut, "description": "Esa cotización ya tenía su tiempo registrado"}},
)
def post_quote_timing(
    data: QuoteTimingCreate, user: CurrentUserDep, db: TenantDB, response: Response
) -> MetricEventOut:
    """Tiempo de una cotización medido por la PWA (inicio y fin). Un solo registro por cotización."""
    event, created = service.record_quote_timing(db, user, data)
    if not created:
        response.status_code = status.HTTP_200_OK
    return _out(event)


@router.post("/manual-baseline", response_model=MetricEventOut, status_code=status.HTTP_201_CREATED)
def post_manual_baseline(data: ManualBaselineCreate, owner: OwnerDep, db: TenantDB) -> MetricEventOut:
    """Medición cronometrada del proceso manual (docs/metrics/protocolo-cotizacion-manual.md). Solo dueña."""
    return _out(service.record_manual_baseline(db, owner, data))


@router.get("/summary", response_model=MetricsSummary)
def get_summary(_owner: OwnerDep, db: TenantDB, date_from: DateFrom = None, date_to: DateTo = None) -> MetricsSummary:
    """Panel de métricas de la pyme, cada cifra con su n. Solo dueña."""
    return service.build_summary(db, service.Window.build(date_from, date_to))


@router.get("/summary.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def get_summary_csv(_owner: OwnerDep, db: TenantDB, date_from: DateFrom = None, date_to: DateTo = None) -> Response:
    """El mismo resumen en CSV (separador `;`, coma decimal) para el informe. Solo dueña."""
    window = service.Window.build(date_from, date_to)
    body = service.summary_csv(service.build_summary(db, window))
    name = f"metricas-caterin-{window.date_to.isoformat()}.csv"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
