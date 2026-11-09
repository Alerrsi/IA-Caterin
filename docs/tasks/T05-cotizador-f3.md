# T05 — Cotizador automatizado
- Estado: hecha (API); pantallas en T08
- Depende de: T04
- Funcionalidad: F3

## Objetivo
Que la emprendedora pegue el mensaje de su cliente ("necesito 80 empanadas y 60 canapés para el sábado") y en pocos minutos tenga la lista de compras, el mejor precio por proveedor y una cotización en PDF lista para enviar, sin rehacer cuentas en Excel.

## Contexto y decisiones previas
- Flujo: `docs/ARCHITECTURE.md` (F3). El LLM solo extrae; todo cálculo es determinista (ADR-002).
- Extractor: `qwen3:4b`, `format` = JSON schema generado desde Pydantic, `temperature` 0.1, `num_predict` 300, un reintento y luego formulario manual (ADR-003).
- Benchmark: 7/8 campos con 3 textos. Pocos casos: la confirmación de la usuaria es obligatoria.
- Supuestos explícitos (a validar con una emprendedora real):
  - Margen: lo fija la usuaria por pyme o por cotización; **no hay margen por defecto inventado**.
  - Redondeo: CLP `ROUND_HALF_UP` por línea y en los totales; las compras se redondean hacia arriba a presentaciones enteras.
  - IVA 19% sobre el neto.
  - El precio al cliente se calcula como costo de insumos × (1 + margen). Mano de obra, gas y transporte **no** se incluyen salvo que la usuaria los agregue como línea manual.

## Entregables
- [x] Esquema Pydantic `ExtractedOrder` (invitados, fecha, ítems con nombre, cantidad y unidad) y extractor detrás de `LLMProvider`.
- [x] `POST /orders/extract`: borrador editable, resolución de nombres contra recetas con `rapidfuzz` y sugerencias si hay ambigüedad.
- [x] `quotes/calculator.py` (funciones puras): insumos necesarios con merma → descuento de stock → faltante → presentaciones a comprar → mejor oferta por insumo con alternativas → costo, margen, IVA y total.
- [x] `POST /orders/{id}/quotes` que guarda `price_snapshot`, `assumptions` y `calc_version`.
- [x] `GET /quotes/{id}/shopping-list` agrupada por proveedor (con los días de despacho).
- [x] `GET /quotes/{id}/pdf`: PDF simple con ReportLab (BSD): datos de la pyme, productos, totales y validez. **Cambio:** no muestra la fecha de los precios de insumos (es información interna); esa fecha está en la lista de compras.
- [x] Registro de inicio y fin de la cotización para la métrica de tiempo (T09).
- [x] Set inicial de ≥ 20 pedidos de ejemplo para el extractor en `ml/evals/extractor/` (sintéticos, marcados como tales).

## Criterios de aceptación
- Con el seed: un pedido de 80 empanadas de pino y 60 canapés produce una cotización cuyas cantidades y totales coinciden con un cálculo a mano documentado en el test.
- Recalcular la misma cotización con los mismos precios da exactamente el mismo resultado; con un precio cambiado, la cotización vieja conserva el suyo.
- Si un insumo no tiene proveedor con precio, la cotización se genera igual, con la línea marcada y un aviso visible.
- Si el extractor falla dos veces, la API responde `extraction_failed` y no queda un borrador corrupto.
- Tiempo de API (sin la extracción): cálculo + PDF p95 < 2 s con el seed en el equipo de referencia (**propuesta**, se mide).

## Pruebas requeridas
- Unitarias del calculador: conversión de unidades, docenas, merma por insumo y por línea, stock suficiente / parcial / cero, redondeo hacia arriba de presentaciones, proveedor sin stock o sin precio, IVA incluido o no, totales con redondeo.
- Pruebas por propiedades (Hypothesis) para invariantes: el total nunca es negativo; más stock nunca aumenta la compra.
- Integración: flujo completo extract → confirm → quote → PDF; aislamiento A/B.
- Evaluación del extractor campo a campo (la amplía T10).

## Fuera de alcance
- Envío por WhatsApp o correo, plantillas con marca, scraping de precios (ROADMAP), facturación.

## Riesgos y preguntas abiertas
- Reglas de redondeo, margen y cómo presentar el IVA: validar con una emprendedora real (pregunta 5 del índice).
- Pedidos en unidades de porciones ("para 50 personas, cóctel") sin cantidades: ¿se ofrece una regla de porciones por persona configurada por la usuaria? No se inventa una por defecto.
- La validez de la cotización (días): ¿la define la usuaria?

## Resumen de cierre
**Qué se hizo (9-nov-2026):**
- `core/llm.py` (`LLMProvider`: Ollama por HTTP, Fake, Disabled; sin LangChain, ver nota en ADR-001), `core/dates.py` (fechas en español de Chile con reglas), `core/matching.py` (rapidfuzz `token_set_ratio`; asociar con ≥ 85 y 10 puntos de ventaja, si no sugerir).
- `modules/quotes`: extractor (prompt fijo `extract-v1`, JSON schema, un reintento, **barrera determinista**: si una cantidad no aparece en el mensaje, la línea queda marcada "Revisa la cantidad"), calculador puro (`CALC_VERSION` 1.1.0), servicio con trazabilidad (snapshot de precios, supuestos, stock, versión de receta, quién la generó), lista de compras por proveedor, PDF sin costos internos, métrica de tiempo de cotización (`metric_event`, `started_at`).
- Decisiones: extraer **no guarda nada**; costo con la presentación más barata por unidad; compra con la de menor total; precio unitario redondeado y subtotal = unitario × cantidad; cotización incompleta (falta un precio) se guarda pero **no genera PDF**; solo la dueña cotiza (propuesta de API.md); margen sin valor por defecto inventado (`margin_required`).
- Evaluación: 22 pedidos sintéticos en `ml/evals/extractor/` + `python -m app.modules.quotes.evaluation`.

**Verificado:**
- 105 pruebas pasan + 1 con LLM real (`RUN_LLM_TESTS=1`, pasa). Incluye un cálculo a mano en `test_hand_calculated_quote_without_stock`, invariantes con Hypothesis (subtotal = unitario × cantidad; total = neto + IVA; más stock nunca aumenta la compra), flujo completo con precio faltante → 409 en el PDF → se agrega el precio → versión 2 completa → PDF con el total correcto y sin nombres de insumos ni costos, cotización antigua que conserva sus precios, validaciones y aislamiento A/B.
- **Extractor con `qwen3:4b` real** (i5-8250U, CPU, 9-nov-2026, antes de agregar la barrera de cantidades): **188/193 campos (97,4 %)**, **18/22 pedidos perfectos**, 0 errores de JSON, 0 reintentos; latencia del LLM p50 **13,7 s**, p95 **22,0 s**; 89 tokens generados (p50). Fallos: inventó "cóctel" como producto (c02), cambió 200 → 201 brochetas (c06) y 50 → 100 canapés (c18), no rescató la fecha en c06 y c21. Los dos errores de cantidad los detecta ahora la barrera determinista. Son 22 casos sintéticos: sirven para detectar problemas, no para fijar un porcentaje.
- Cálculo + PDF por la API (sin LLM): p50 0,07 s, p95 0,12 s en 20 repeticiones (incluye el `curl` y el parseo), bajo la meta propuesta de 2 s.
- Prueba manual: pedido real por texto → 80 empanadas de pino + 4 docenas de brochetas → total $155.552 → PDF revisado a la vista (cuadra).

**Pendiente / riesgos:**
- La extracción tarda 14–22 s en CPU: en la pantalla hay que mostrar que está trabajando, y T10 debe probar `qwen3:4b-instruct` y Gemma 4 E4B.
- Reglas de redondeo, margen, IVA en los costos y "más barato" como criterio: validar con una emprendedora real.
- Pedidos en porciones ("para 50 personas") no se calculan: se pide la cantidad.
- No se mide aún el tiempo de cotización manual de referencia (T09).
