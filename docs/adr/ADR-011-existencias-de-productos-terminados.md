# ADR-011 — Existencias de productos terminados y consumo de insumos al producir

- Estado: **aceptado** (16-nov-2026; el usuario pidió implementar el plan de T18)
- Contexto en: `docs/tasks/T18-existencias-por-foto.md`, ADR-004 (libro de movimientos), ADR-002 (cálculo determinista)

## Contexto

Hasta T18, confirmar el conteo de la foto (F2) solo guardaba un `production_record`. El inventario tenía solo insumos:
no había dónde quedaran "48 empanadas de pino listas" y los insumos usados no se descontaban, aunque el motivo de
movimiento `production` ya existía. AGENTS.md (F2) pide que el conteo "se registre en producción/inventario".

## Decisión

1. **El producto terminado es la receta final.** Su saldo vive en `recipe.stock_qty`, en la unidad de rendimiento
   (unidad, g o ml). No se crea un insumo espejo por producto: se mezclaría con costos, listas de compra y cotizaciones.
2. **Libro propio que solo crece:** `product_movement` (motivos `production`, `delivery`, `adjustment`, `waste`,
   `void`), igual que `stock_movement` para insumos (ADR-004). El saldo se actualiza con una suma atómica en la base y
   siempre es igual a la suma del libro (hay una prueba que lo verifica).
3. **Al confirmar una producción**, en una sola transacción e idempotente por `Idempotency-Key`:
   - suma `confirmed_qty` al producto (`production`);
   - si la pyme lo tiene activo (`pyme.production_consumes_ingredients`, por defecto sí) o el pedido lo indica
     (`consume_ingredients`), descuenta cada insumo de la receta con `required_qty` (la misma fórmula y merma que la
     cotización), como `stock_movement` `production` negativos referenciados a la producción.
4. **Un insumo puede quedar negativo**; se avisa antes (vista previa) y en la respuesta (`went_negative`). Bloquear
   haría perder el conteo.
5. **Corregir es anular:** `POST /vision/productions/{id}/void` (solo dueña) aplica los movimientos inversos de todo
   lo que esa producción movió y marca `voided_at`. El libro no se reescribe.
6. **Pedido entregado = salida de producto.** `quotes.update_order` llama a `sync_order_delivery`: compara lo que
   debería estar descontado (si está `delivered`) con lo ya aplicado por la referencia `('order', id)` y aplica solo
   la diferencia. Así cambiar el estado o las líneas nunca descuenta dos veces, y volver atrás lo devuelve.
7. **Dueño del código:** el módulo `inventory` es dueño de los dos libros (insumos y productos) y lee `recipe` para el
   saldo de productos. `vision` y `quotes` lo usan a través de `inventory/service.py`.
8. **El asistente** responde "¿cuántas empanadas tengo listas?" con la intención `product_stock` (nivel 0, sin LLM).
   El saldo **no** se agrega a las fichas del RAG (ADR-006): cambiaría con cada producción y obligaría a re-vectorizar
   la ficha de la receta cada vez.

## Consecuencias

- La foto ahorra dos trabajos: contar y anotar el inventario.
- Si una receta está mal cargada, el descuento automático deja mal el stock de insumos. Mitigación: vista previa con
  el detalle, casilla para no descontar en cada confirmación, ajuste de la pyme y anulación.
- Las producciones anteriores a T18 quedan como estaban (`consumed_ingredients = false`, sin movimientos): no se
  reescribe el pasado. Anular una de ellas solo la marca como anulada.
- La cotización todavía no usa el producto terminado antes de pedir insumos: cambia el cálculo de F3 y su
  `calc_version` (propuesta T20).
