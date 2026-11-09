# T05 — Cotizador automatizado
- Estado: pendiente
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
- [ ] Esquema Pydantic `ExtractedOrder` (invitados, fecha, ítems con nombre, cantidad y unidad) y extractor detrás de `LLMProvider`.
- [ ] `POST /orders/extract`: borrador editable, resolución de nombres contra recetas con `rapidfuzz` y sugerencias si hay ambigüedad.
- [ ] `quotes/calculator.py` (funciones puras): insumos necesarios con merma → descuento de stock → faltante → presentaciones a comprar → mejor oferta por insumo con alternativas → costo, margen, IVA y total.
- [ ] `POST /orders/{id}/quotes` que guarda `price_snapshot`, `assumptions` y `calc_version`.
- [ ] `GET /quotes/{id}/shopping-list` agrupada por proveedor (con los días de despacho).
- [ ] `GET /quotes/{id}/pdf`: PDF simple y legible en el celular (librería con licencia permisiva, p. ej. WeasyPrint (BSD) o ReportLab (BSD)), con los datos de la pyme, el detalle, los totales, la validez y la fecha de los precios.
- [ ] Registro de inicio y fin de la cotización para la métrica de tiempo (T09).
- [ ] Set inicial de ≥ 20 pedidos de ejemplo para el extractor en `ml/evals/extractor/` (sintéticos, marcados como tales).

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
(se completa al terminar)
