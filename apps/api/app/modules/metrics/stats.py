"""Agregaciones puras del panel de métricas (T09). Sin base de datos, para probarlas sin rodeos.

Los percentiles usan interpolación lineal entre rangos, igual que `percentile_cont` de Postgres:
así las cifras del panel se pueden verificar con una consulta SQL directa.
"""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal

LOW_N_THRESHOLD = 5
"""Bajo este número de mediciones el panel advierte que la cifra no es sólida (estudio piloto)."""


def _sorted(values: Iterable[Decimal | int | float]) -> list[Decimal]:
    return sorted(Decimal(str(v)) for v in values)


def percentile(values: Iterable[Decimal | int | float], q: float) -> Decimal | None:
    """Percentil `q` (0 a 1) con interpolación lineal. None si no hay datos."""
    if not 0 <= q <= 1:
        raise ValueError("q debe estar entre 0 y 1")
    data = _sorted(values)
    if not data:
        return None
    pos = Decimal(str(q)) * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def median(values: Iterable[Decimal | int | float]) -> Decimal | None:
    return percentile(values, 0.5)


def mean(values: Sequence[Decimal | int | float]) -> Decimal | None:
    if not values:
        return None
    return sum((Decimal(str(v)) for v in values), Decimal(0)) / len(values)


def share_pct(part: int, total: int) -> Decimal | None:
    """Porcentaje 0 a 100. None si no hay total (no se inventa un 0 %)."""
    if total <= 0:
        return None
    return Decimal(part) * 100 / Decimal(total)


def rounded(value: Decimal | None, places: int) -> float | None:
    """Redondeo comercial (mitad hacia arriba) para mostrar; la cuenta se hace antes, con Decimal."""
    if value is None:
        return None
    return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def is_low_n(n: int) -> bool:
    return n < LOW_N_THRESHOLD
