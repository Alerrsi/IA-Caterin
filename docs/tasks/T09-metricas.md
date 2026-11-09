# T09 — Métricas de éxito
- Estado: pendiente
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
- [ ] `POST /metrics/survey`, `POST /metrics/quote-timing`, `POST /metrics/manual-baseline`, `GET /metrics/summary`.
- [ ] Protocolo de medición del tiempo manual (`docs/metrics/protocolo-cotizacion-manual.md`): mismo pedido, misma persona o personas comparables, cronómetro desde que recibe el pedido hasta tener el total; cuántas repeticiones; cómo se anota.
- [ ] Protocolo para "buscar el dato a mano" en el asistente (p. ej. abrir la planilla y encontrar el stock de un insumo).
- [ ] Panel simple en la PWA (solo dueña) y una vista agregada para el equipo: satisfacción promedio y n, mediana del tiempo de cotización antes/después, latencia p50/p95 por nivel, % sin LLM, % de degradaciones.
- [ ] Exportación CSV de las métricas para el informe.

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
(se completa al terminar)
