"""Vista agregada para el equipo (T09): el mismo resumen, sumando todas las pymes.

No pasa por la API ni por el JWT: se corre en el servidor con acceso a la base.

    python -m app.modules.metrics.report --from 2026-11-01 --exclude-demo
    python -m app.modules.metrics.report --csv > metricas.csv
"""

import argparse
import sys
from datetime import date

from app.db.session import get_sessionmaker
from app.modules.metrics import service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumen de métricas de todas las pymes")
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat, default=None)
    parser.add_argument("--to", dest="date_to", type=date.fromisoformat, default=None)
    parser.add_argument("--exclude-demo", action="store_true", help="Excluye las pymes de demo (datos sintéticos)")
    parser.add_argument("--csv", action="store_true", help="Salida CSV en vez de JSON")
    args = parser.parse_args(argv)
    window = service.Window.build(args.date_from, args.date_to)
    with get_sessionmaker()() as db:
        summary = service.build_summary(db, window, service.Scope(exclude_demo=args.exclude_demo))
    sys.stdout.write(service.summary_csv(summary) if args.csv else summary.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
