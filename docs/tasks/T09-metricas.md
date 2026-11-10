# T09 — Métricas de éxito
- Estado: hecha (9-nov-2026; las métricas del asistente quedan vacías hasta T07)
- Depende de: T05, T07, T08
- Funcionalidad: transversal

## Objetivo
Demostrar con números medidos, no supuestos, si Cáterin le ahorra tiempo a la emprendedora y si le gusta usarlo.

## Contexto y decisiones previas
- Métricas del README: satisfacción (1 a 5 estrellas), tiempo de cotización antes/después y tiempo de respuesta del asistente frente a buscar el dato a mano.
- Se agrega, desde ADR-005: latencia por nivel y **porcentaje de consultas resueltas sin LLM**.
- Datos en `metric_event` y `assistant_interaction` (DATA_MODEL).
- Honestidad: el tiempo "antes" se **mide** con un proceso manual de referencia; no se toma de cifras de Winnow, MarketMan ni del informe (`AGENTS.md`, sección 10).

## Entregables
- [x] `POST /metrics/survey`, `POST /metrics/quote-timing`, `POST /metrics/manual-baseline`, `GET /metrics/summary`.
- [x] Protocolo de medición del tiempo manual (`docs/metrics/protocolo-cotizacion-manual.md`): mismo pedido, misma persona o personas comparables, cronómetro desde que recibe el pedido hasta tener el total; cuántas repeticiones; cómo se anota.
- [x] Protocolo para "buscar el dato a mano" en el asistente (p. ej. abrir la planilla y encontrar el stock de un insumo).
- [x] Panel simple en la PWA (solo dueña) y una vista agregada para el equipo: satisfacción promedio y n, mediana del tiempo de cotización antes/después, latencia p50/p95 por nivel, % sin LLM, % de degradaciones.
- [x] Exportación CSV de las métricas para el informe.

## Criterios de aceptación
- El panel muestra cada métrica con su **n** y su periodo; si n es bajo (p. ej. < 5), lo advierte.
- El tiempo de cotización con Cáterin se mide automáticamente (inicio y fin en la PWA) y se puede comparar con al menos una medición manual registrada.
- Las cifras del panel coinciden con una consulta SQL directa sobre los eventos (test).

## Pruebas requeridas
- Unitarias: agregaciones (medianas, percentiles, % sin LLM).
- Integración: endpoints, solo la dueña ve el panel, aislamiento A/B.

## Fuera de alcance
- Analítica de producto de terceros (Google Analytics, etc.).

## Riesgos y preguntas abiertas
- Con pocas usuarias reales las cifras no serán estadísticamente sólidas; reportarlas como estudio piloto con n explícito.
- Si la métrica no alcanza lo esperado, se reporta tal cual y se proponen mejoras, sin ajustar el criterio (`AGENTS.md`, sección 10).

## Resumen de cierre
**Qué se hizo (9-nov-2026):**
- `modules/metrics`: `POST /metrics/survey`, `POST /metrics/quote-timing` (idempotente por `quote_id`, máximo 24 h), `POST /metrics/manual-baseline` (solo dueña), `GET /metrics/summary` y `GET /metrics/summary.csv` (solo dueña, filtro `from`/`to` en días de Chile).
- Agregaciones puras en `stats.py` con `Decimal`: mediana y percentiles con interpolación lineal (igual que `percentile_cont`), promedio, porcentajes que dan `null` sin datos (nunca un 0 % inventado) y bandera `low_n` (n < 5) en cada cifra, más una lista de advertencias en español.
- Definiciones: "sin LLM" = nivel 0; "degradada" = `fallback_reason` no nulo. Las mediciones manuales no se recortan por periodo (son la línea base) y se muestran con sus fechas de medición.
- Vista del equipo: `python -m app.modules.metrics.report [--from] [--to] [--exclude-demo] [--csv]` suma todas las pymes desde el servidor, sin pasar por la API.
- PWA: la pantalla **Cotizar** mide desde que se abre hasta que llega la cotización y lo envía a `/metrics/quote-timing` sin bloquear a la usuaria; encuesta de estrellas al pie de cada cotización; pantalla **Mis métricas** (solo dueña) con n, periodo, advertencias, descarga CSV y formulario para registrar mediciones manuales.
- Índice `ix_assistant_interaction_pyme_created` (migración `3c1f9a7d2b10`). Protocolo en `docs/metrics/protocolo-cotizacion-manual.md`.

**Verificado:**
- `./scripts/check.sh` en verde: 119 pruebas de API (1 omitida, la del LLM real) con 94 % de cobertura total y 99–100 % en `modules/metrics`; 16 pruebas web.
- Pruebas de T09: unitarias de medianas, percentiles y porcentajes; endpoints y validaciones; solo la dueña ve el panel y registra la línea base; aislamiento A/B (el resumen de A no cuenta nada de B y una cotización de B da 404); **las cifras del resumen coinciden con SQL directo** (`avg`, `percentile_cont`, `count(*) FILTER`) sobre `metric_event` y `assistant_interaction`; filtro por periodo; CSV; informe del equipo con y sin demo.
- Revisado a mano en la PWA (375 px, sin scroll horizontal) contra la API de desarrollo: panel vacío con sus advertencias y CSV con BOM.

**Pendiente / riesgos:**
- **No hay mediciones reales.** Ni de la cotización manual ni de buscar un dato: el panel lo advierte. Hace falta una emprendedora (pregunta abierta 6 del índice) para aplicar el protocolo; con la pyme de demo cualquier cifra es sintética y así debe informarse.
- Las métricas del asistente (latencia por nivel, % sin LLM, % degradadas, buscar un dato) quedan en `n = 0` hasta que T07 escriba `assistant_interaction`. La latencia de visión (`vision_latency`) queda para T06.
- Sin conexión, el tiempo de cotización y la encuesta se pierden (no hay cola offline); se cotiza solo con red, así que el impacto es bajo.
- El tiempo con Cáterin empieza al abrir la pantalla y termina al llegar la cotización: no incluye revisar el PDF ni enviarlo, igual que la medición manual (protocolo, sección 2).
- La encuesta aparece al pie de cada cotización: si molesta a las usuarias, mostrarla una vez por semana (decisión de producto).
