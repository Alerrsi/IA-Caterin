"""T09: agregaciones puras, endpoints de métricas, permisos, aislamiento A/B y cifras contra SQL directo."""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import MetricKind
from app.db.models import AssistantInteraction, MetricEvent, Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.metrics import report, stats
from app.modules.metrics.service import TZ
from tests.helpers import PASSWORD, Tenant, login, register

API = "/api/v1"


# --------------------------------------------------------------------------- unitarias


def test_median_odd_even_and_empty() -> None:
    assert stats.median([3, 1, 2]) == 2
    assert stats.median([4, 1, 3, 2]) == Decimal("2.5")
    assert stats.median([]) is None
    assert stats.median([Decimal("7.5")]) == Decimal("7.5")


def test_percentile_interpolates_like_percentile_cont() -> None:
    values = list(range(1, 21))  # 1..20
    assert stats.percentile(values, 0.5) == Decimal("10.5")
    assert stats.percentile(values, 0.95) == Decimal("19.05")
    assert stats.percentile(values, 0) == 1
    assert stats.percentile(values, 1) == 20
    assert stats.percentile([100, 300], 0.95) == Decimal("290")
    with pytest.raises(ValueError):
        stats.percentile(values, 1.5)


def test_mean_share_and_rounding() -> None:
    assert stats.mean([5, 4, 4]) == Decimal(13) / 3
    assert stats.rounded(stats.mean([5, 4, 4]), 2) == 4.33
    assert stats.share_pct(2, 3) is not None
    assert stats.rounded(stats.share_pct(2, 3), 1) == 66.7
    assert stats.share_pct(0, 0) is None  # sin consultas no hay porcentaje, ni siquiera 0 %
    assert stats.rounded(Decimal("2.25"), 1) == 2.3  # mitad hacia arriba, no al par
    assert stats.is_low_n(4) and not stats.is_low_n(5)


# --------------------------------------------------------------------------- fixtures


def _collaborator(client: TestClient, owner: Tenant, email: str) -> dict[str, str]:
    resp = client.post(
        f"{API}/users", headers=owner.headers, json={"email": email, "full_name": "Colaboradora", "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    return login(client, email)


@pytest.fixture
def two(client: TestClient) -> tuple[Tenant, Tenant]:
    return register(client, "Pyme A", "a@metricas.cl"), register(client, "Pyme B", "b@metricas.cl")


def _timing(client: TestClient, headers: dict[str, str], seconds: float, **extra: object) -> dict:  # type: ignore[type-arg]
    end = datetime.now(UTC)
    body = {"started_at": (end - timedelta(seconds=seconds)).isoformat(), "ended_at": end.isoformat(), **extra}
    resp = client.post(f"{API}/metrics/quote-timing", headers=headers, json=body)
    assert resp.status_code in (200, 201), resp.text
    return dict(resp.json())


def _baseline(client: TestClient, headers: dict[str, str], seconds: float, task: str = "quote", rep: int = 1) -> None:
    body = {"task": task, "seconds": seconds, "reference": "pedido de referencia P1", "repetition": rep,
            "measured_on": "2026-11-02", "tool": "Excel"}  # fmt: skip
    resp = client.post(f"{API}/metrics/manual-baseline", headers=headers, json=body)
    assert resp.status_code == 201, resp.text


def _interaction(
    db: Session, t: Tenant, level: int, latency_ms: int, fallback: str | None = None, **kw: object
) -> None:
    db.add(
        AssistantInteraction(
            pyme_id=uuid.UUID(t.pyme_id),
            user_id=uuid.UUID(t.user_id),
            question="dato sintético de prueba",
            level=level,
            latency_ms=latency_ms,
            fallback_reason=fallback,
            **kw,
        )
    )


# --------------------------------------------------------------------------- endpoints


def test_survey_validates_stars_and_stores_comment(client: TestClient, two: tuple[Tenant, Tenant], db: Session) -> None:
    a, _ = two
    for bad in (0, 6):
        assert client.post(f"{API}/metrics/survey", headers=a.headers, json={"stars": bad}).status_code == 422
    resp = client.post(
        f"{API}/metrics/survey", headers=a.headers, json={"stars": 4, "comment": " Rápido ", "context": "quote"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["kind"] == "survey" and resp.json()["value_num"] == 4
    event = db.scalars(select(MetricEvent)).one()
    assert event.payload == {"context": "quote", "comment": "Rápido"}
    assert str(event.user_id) == a.user_id and str(event.pyme_id) == a.pyme_id
    assert client.post(f"{API}/metrics/survey", json={"stars": 4}).status_code == 401


def test_quote_timing_validations(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, _ = two
    now = datetime.now(UTC)
    url = f"{API}/metrics/quote-timing"
    backwards = {"started_at": now.isoformat(), "ended_at": (now - timedelta(seconds=5)).isoformat()}
    assert client.post(url, headers=a.headers, json=backwards).status_code == 422
    naive = {"started_at": "2026-11-09T10:00:00", "ended_at": "2026-11-09T10:05:00"}
    assert client.post(url, headers=a.headers, json=naive).status_code == 422
    too_long = {"started_at": (now - timedelta(hours=25)).isoformat(), "ended_at": now.isoformat()}
    assert client.post(url, headers=a.headers, json=too_long).json()["code"] == "timing_out_of_range"
    assert _timing(client, a.headers, 95.04, source="form")["value_num"] == 95.0


def test_quote_timing_with_quote_is_idempotent_and_isolated(client: TestClient, db: Session) -> None:
    seed(db)
    owner = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    recipe_id = str(db.scalars(select(Recipe.id)).first())
    order = client.post(
        f"{API}/orders",
        headers=owner,
        json={"customer_name": "Cliente", "lines": [{"recipe_id": recipe_id, "qty": "24", "unit": "unit"}]},
    ).json()
    quote = client.post(f"{API}/orders/{order['id']}/quotes", headers=owner, json={}).json()

    first = _timing(client, owner, 180, quote_id=quote["id"], source="text")
    end = datetime.now(UTC)
    again = client.post(
        f"{API}/metrics/quote-timing",
        headers=owner,
        json={
            "started_at": (end - timedelta(seconds=10)).isoformat(),
            "ended_at": end.isoformat(),
            "quote_id": quote["id"],
        },
    )
    assert again.status_code == 200 and again.json()["id"] == first["id"]  # no se cuenta dos veces
    event = db.scalars(select(MetricEvent).where(MetricEvent.kind == MetricKind.QUOTE_TIMING)).one()
    assert event.payload["quote_id"] == quote["id"] and event.payload["order_id"] == order["id"]

    intruder = register(client, "Pyme Intrusa", "intrusa@metricas.cl")
    resp = client.post(
        f"{API}/metrics/quote-timing",
        headers=intruder.headers,
        json={
            "started_at": (end - timedelta(seconds=10)).isoformat(),
            "ended_at": end.isoformat(),
            "quote_id": quote["id"],
        },
    )
    assert resp.status_code == 404  # la cotización de otra pyme no existe para ella


def test_only_owner_sees_summary_and_records_baseline(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, _ = two
    colab = _collaborator(client, a, "colab@metricas.cl")
    assert client.get(f"{API}/metrics/summary", headers=colab).status_code == 403
    assert client.get(f"{API}/metrics/summary.csv", headers=colab).status_code == 403
    body = {"task": "quote", "seconds": 600, "reference": "P1", "measured_on": "2026-11-02"}
    assert client.post(f"{API}/metrics/manual-baseline", headers=colab, json=body).status_code == 403
    # la colaboradora sí puede responder la encuesta y su cotización sí se cronometra
    assert client.post(f"{API}/metrics/survey", headers=colab, json={"stars": 5}).status_code == 201
    _timing(client, colab, 120)
    assert client.get(f"{API}/metrics/summary", headers=a.headers).status_code == 200
    assert client.post(f"{API}/metrics/manual-baseline", headers=a.headers, json=body).status_code == 201


def test_manual_baseline_validations(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, _ = two
    url = f"{API}/metrics/manual-baseline"
    ok = {"task": "data_lookup", "seconds": 45, "reference": "stock de harina", "measured_on": "2026-11-03"}
    for bad in ({**ok, "seconds": 0}, {**ok, "task": "otra"}, {**ok, "reference": ""}, {**ok, "repetition": 0}):
        assert client.post(url, headers=a.headers, json=bad).status_code == 422
    assert client.post(url, headers=a.headers, json=ok).status_code == 201


def test_empty_summary_warns_and_invents_nothing(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, _ = two
    s = client.get(f"{API}/metrics/summary", headers=a.headers).json()
    assert s["satisfaction"] == {"n": 0, "mean_stars": None, "distribution": dict.fromkeys("12345", 0), "low_n": True}
    assert s["quote_time"]["caterin_median"]["value"] is None
    assert s["assistant"]["total"] == 0 and s["assistant"]["without_llm"]["pct"] is None
    assert [lv["level"] for lv in s["assistant"]["levels"]] == [0, 1, 2]
    assert any("medición manual de referencia" in w for w in s["warnings"])
    assert not any("solo 0" in w for w in s["warnings"])
    assert "Satisfacción: todavía no hay respuestas a la encuesta." in s["warnings"]
    assert s["low_n_threshold"] == 5
    assert s["period"]["date_from"] is None and s["period"]["date_to"] == datetime.now(TZ).date().isoformat()


def test_summary_is_isolated_between_pymes(client: TestClient, two: tuple[Tenant, Tenant], db: Session) -> None:
    a, b = two
    for stars in (5, 4):
        client.post(f"{API}/metrics/survey", headers=a.headers, json={"stars": stars})
    client.post(f"{API}/metrics/survey", headers=b.headers, json={"stars": 1})
    _timing(client, a.headers, 100)
    _timing(client, b.headers, 9000)
    _baseline(client, b.headers, 5000)
    _interaction(db, a, 0, 200)
    _interaction(db, b, 1, 9000, "llm_timeout")
    db.commit()

    sa = client.get(f"{API}/metrics/summary", headers=a.headers).json()
    assert sa["satisfaction"]["n"] == 2 and sa["satisfaction"]["mean_stars"] == 4.5
    assert sa["quote_time"]["caterin_median"] == {"n": 1, "value": 100.0, "unit": "s", "low_n": True}
    assert sa["quote_time"]["manual_median"]["n"] == 0
    assert sa["assistant"]["total"] == 1 and sa["assistant"]["degraded"]["n"] == 0

    sb = client.get(f"{API}/metrics/summary", headers=b.headers).json()
    assert sb["satisfaction"]["mean_stars"] == 1.0
    assert sb["quote_time"]["manual_median"]["value"] == 5000.0
    assert sb["assistant"]["without_llm"]["pct"] == 0.0 and sb["assistant"]["degraded"]["pct"] == 100.0


def test_summary_period_filters_use_events_but_keep_baseline(
    client: TestClient, two: tuple[Tenant, Tenant], db: Session
) -> None:
    a, _ = two
    _baseline(client, a.headers, 900)
    _timing(client, a.headers, 60)
    old = datetime(2026, 10, 1, 12, tzinfo=UTC)
    db.add(
        MetricEvent(pyme_id=uuid.UUID(a.pyme_id), kind=MetricKind.QUOTE_TIMING, value_num=Decimal(999), created_at=old)
    )
    _interaction(db, a, 0, 100, created_at=old)
    db.commit()

    today = datetime.now(TZ).date()
    recent = client.get(f"{API}/metrics/summary?from={today - timedelta(days=7)}", headers=a.headers).json()
    assert recent["quote_time"]["caterin_median"]["n"] == 1
    assert recent["quote_time"]["manual_median"]["n"] == 1  # la línea base no se recorta
    assert recent["quote_time"]["manual_range"] == {"first_measured_on": "2026-11-02", "last_measured_on": "2026-11-02"}
    assert recent["assistant"]["total"] == 0
    october = client.get(f"{API}/metrics/summary?from=2026-10-01&to=2026-10-31", headers=a.headers).json()
    assert october["quote_time"]["caterin_median"] == {"n": 1, "value": 999.0, "unit": "s", "low_n": True}
    assert october["assistant"]["total"] == 1
    assert october["period"] == {"date_from": "2026-10-01", "date_to": "2026-10-31", "timezone": "America/Santiago"}
    bad = client.get(f"{API}/metrics/summary?from=2026-11-05&to=2026-11-01", headers=a.headers)
    assert bad.status_code == 422 and bad.json()["code"] == "bad_period"


def _seed_mixed(client: TestClient, db: Session, a: Tenant, b: Tenant) -> None:
    for stars in (5, 4, 4, 3, 5, 2):
        client.post(f"{API}/metrics/survey", headers=a.headers, json={"stars": stars})
    for s in (310, 95.5, 140, 220, 180.2, 75):
        _timing(client, a.headers, s)
    for rep, s in enumerate((1500, 1320, 1710), start=1):
        _baseline(client, a.headers, s, rep=rep)
    for rep, s in enumerate((62, 48), start=1):
        _baseline(client, a.headers, s, task="data_lookup", rep=rep)
    for i, ms in enumerate((120, 180, 95, 300, 140, 1300, 210)):
        _interaction(db, a, 0, ms, cache_hit=i % 2 == 0)
    for ms, fb in ((8200, None), (11050, None), (13900, "numbers_mismatch"), (16100, "llm_timeout")):
        _interaction(db, a, 1, ms, fb)
    _interaction(db, a, 2, 12500)
    # ruido de la pyme B que no debe contarse
    client.post(f"{API}/metrics/survey", headers=b.headers, json={"stars": 1})
    _timing(client, b.headers, 5000)
    _interaction(db, b, 0, 99999)
    db.commit()


def test_summary_matches_direct_sql(client: TestClient, two: tuple[Tenant, Tenant], db: Session) -> None:
    a, b = two
    _seed_mixed(client, db, a, b)
    s = client.get(f"{API}/metrics/summary", headers=a.headers).json()
    p = {"p": a.pyme_id}

    def one(sql: str, **extra: object) -> Decimal | None:
        value = db.execute(text(sql), {**p, **extra}).scalar()
        return None if value is None else Decimal(str(value))

    sat = one("SELECT avg(value_num) FROM metric_event WHERE pyme_id = :p AND kind = 'survey'")
    n_sat = one("SELECT count(*) FROM metric_event WHERE pyme_id = :p AND kind = 'survey'")
    assert (s["satisfaction"]["n"], s["satisfaction"]["mean_stars"]) == (n_sat, stats.rounded(sat, 2))
    dist = db.execute(
        text("SELECT value_num::int, count(*) FROM metric_event WHERE pyme_id = :p AND kind = 'survey' GROUP BY 1"), p
    ).all()
    assert {k: v for k, v in s["satisfaction"]["distribution"].items() if v} == {str(k): v for k, v in dist}

    med_q = one(
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY value_num) FROM metric_event"
        " WHERE pyme_id = :p AND kind = 'quote_timing'"
    )
    assert s["quote_time"]["caterin_median"]["value"] == stats.rounded(med_q, 1)
    for task, key in (("quote", "quote_time"), ("data_lookup", "data_lookup")):
        med = one(
            "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY value_num) FROM metric_event"
            " WHERE pyme_id = :p AND kind = 'manual_baseline' AND payload->>'task' = :task",
            task=task,
        )
        assert s[key]["manual_median"]["value"] == stats.rounded(med, 1)
    med_assist = one(
        "SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms / 1000.0) FROM assistant_interaction"
        " WHERE pyme_id = :p"
    )
    assert s["data_lookup"]["assistant_median"]["value"] == stats.rounded(med_assist, 2)

    rows = db.execute(
        text(
            "SELECT level, count(*),"
            " percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),"
            " percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)"
            " FROM assistant_interaction WHERE pyme_id = :p GROUP BY level ORDER BY level"
        ),
        p,
    ).all()
    levels = {lv["level"]: lv for lv in s["assistant"]["levels"]}
    for level, n, p50, p95 in rows:
        assert levels[level]["n"] == n
        assert levels[level]["p50_ms"] == stats.rounded(Decimal(str(p50)), 0)
        assert levels[level]["p95_ms"] == stats.rounded(Decimal(str(p95)), 0)

    pct_no_llm = one(
        "SELECT count(*) FILTER (WHERE level = 0) * 100.0 / count(*) FROM assistant_interaction WHERE pyme_id = :p"
    )
    pct_degraded = one(
        "SELECT count(*) FILTER (WHERE fallback_reason IS NOT NULL) * 100.0 / count(*)"
        " FROM assistant_interaction WHERE pyme_id = :p"
    )
    assert s["assistant"]["total"] == 12
    assert s["assistant"]["without_llm"]["pct"] == stats.rounded(pct_no_llm, 1) == 58.3
    assert s["assistant"]["degraded"]["pct"] == stats.rounded(pct_degraded, 1) == 16.7
    # con n >= 5 no hay advertencia de n bajo en lo que sí tiene datos suficientes
    assert s["satisfaction"]["low_n"] is False and s["quote_time"]["caterin_median"]["low_n"] is False
    assert s["quote_time"]["manual_median"]["low_n"] is True  # solo 3 mediciones manuales
    assert any("Cotización manual de referencia: solo 3" in w for w in s["warnings"])


def test_summary_csv_export(client: TestClient, two: tuple[Tenant, Tenant], db: Session) -> None:
    a, b = two
    _seed_mixed(client, db, a, b)
    resp = client.get(f"{API}/metrics/summary.csv?from=2026-11-01", headers=a.headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    content = resp.content.decode("utf-8")
    assert content.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(content.lstrip("﻿")), delimiter=";"))
    by_key = {(r["seccion"], r["metrica"], r["segmento"]): r for r in rows}
    summary = client.get(f"{API}/metrics/summary?from=2026-11-01", headers=a.headers).json()
    sat = by_key[("satisfaccion", "promedio_estrellas", "")]
    assert sat["n"] == "6" and sat["valor"] == f"{summary['satisfaction']['mean_stars']:g}".replace(".", ",")
    assert sat["desde"] == "2026-11-01" and sat["n_bajo"] == "no"
    manual = by_key[("tiempo_cotizacion", "mediana", "manual")]
    assert manual["valor"] == "1500" and manual["n_bajo"] == "si" and manual["desde"] == "2026-11-02"
    assert by_key[("asistente", "pct_sin_llm", "")]["valor"] == "58,3"
    assert ("asistente", "latencia_p95", "nivel_1") in by_key


def test_team_report_aggregates_and_can_exclude_demo(
    client: TestClient, two: tuple[Tenant, Tenant], db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    a, b = two
    client.post(f"{API}/metrics/survey", headers=a.headers, json={"stars": 5})
    client.post(f"{API}/metrics/survey", headers=b.headers, json={"stars": 3})
    seed(db)
    demo = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    client.post(f"{API}/metrics/survey", headers=demo, json={"stars": 1})

    assert report.main([]) == 0
    assert '"n": 3' in capsys.readouterr().out
    assert report.main(["--exclude-demo", "--csv"]) == 0
    out = capsys.readouterr().out
    row = next(r for r in csv.reader(io.StringIO(out.lstrip("﻿")), delimiter=";") if r[1] == "promedio_estrellas")
    assert row[3:5] == ["2", "4"]
