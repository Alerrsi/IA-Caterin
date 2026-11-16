# T18 — Existencias de productos terminados desde la foto
- Estado: hecha en la rama `feat/T18-existencias-por-foto` (16-nov-2026); falta integrar a `main`
- Depende de: T04 (inventario y libro de movimientos), T06 (conteo por foto), T08 (cola sin red)
- Funcionalidad: F2 (con efecto en inventario)
- Decisión: [ADR-011](../adr/ADR-011-existencias-de-productos-terminados.md) (aceptado)

## Objetivo
Que al confirmar el conteo de una bandeja, las empanadas o canapés contados queden como **existencias listas para
entregar**, y que los insumos que se usaron para hacerlos se **descuenten solos** del inventario. Así la foto ahorra
dos trabajos: contar y anotar.

## Diagnóstico (16-nov-2026): hoy la foto NO ingresa nada al inventario
Revisado en el código:

| Pieza | Qué hace hoy | Qué falta |
|-------|--------------|-----------|
| `POST /vision/count` | Detecta y cuenta por clase, y une cada clase con su receta (`recipe.vision_class`) | — |
| `POST /vision/productions` (`vision/service.py: confirm_production`) | Guarda un `production_record` (detectado, confirmado, corrección, versión del modelo, cajas) y sube la versión de datos `production` | No crea ningún `stock_movement` ni toca `ingredient.stock_qty` |
| Inventario (`ingredient`, `stock_movement`) | Solo existen **insumos**. No hay existencias de productos terminados | Un lugar donde viva el stock de "empanadas de pino listas" |
| `MovementReason.PRODUCTION` | Existe en el enum, y la API rechaza que la usuaria lo use a mano ("lo registra el sistema"), pero **ningún código lo genera** | El consumo de insumos al producir |
| PWA (`pages/Vision.tsx`) | Encola un `POST /vision/productions` por producto y dice "Producción registrada" | Mostrar qué se suma y qué se descuenta antes de confirmar |
| Asistente | "¿Cuánto produje hoy?" suma `production_record` | "¿Cuántas empanadas tengo listas?" |

Conclusión: el conteo queda como **registro histórico de producción**, pero ni suma productos al inventario ni descuenta
los insumos usados. La documentación de AGENTS.md (F2: "se registra en producción/inventario") quedó cumplida solo en
su primera mitad.

## Supuestos (decididos sin preguntar; ver memoria "decidir detalles sin preguntar")
1. **Las existencias de producto terminado son por receta final** (`recipe.is_final_product = true`), en unidades
   (la foto cuenta unidades). No se crea un "insumo espejo" por producto: se mezclarían en listas, costos y
   cotizaciones.
2. **Mismo patrón que los insumos (ADR-004):** un libro de movimientos que solo crece (`product_movement`) es la fuente
   de verdad y `recipe.stock_qty` es el saldo, actualizado con suma atómica en la base.
3. **Al confirmar se descuentan los insumos por defecto**, con `required_qty` de `recipes/costing.py` (incluye merma),
   como movimientos `production` negativos referenciados al registro. La dueña lo puede apagar en Ajustes
   (`pyme.production_consumes_ingredients`), y en cada confirmación hay una casilla para no descontar esa vez (p. ej.
   si ya lo ajustó a mano). El cálculo es código determinista; la visión solo aporta la cantidad confirmada.
4. **Se permite que un insumo quede negativo** y se avisa ("Harina quedó en −200 g: revisa el stock"). Bloquear la
   confirmación por un stock mal cargado haría perder el conteo, que es lo valioso.
5. **Todo en una transacción e idempotente:** registro + suma de producto + descuentos de insumos se guardan juntos.
   Con la misma `Idempotency-Key` (la cola sin red reintenta) no se duplica nada.
6. **Corregir después = anular, no editar:** `POST /vision/productions/{id}/void` crea los movimientos inversos y marca
   `voided_at`. El libro nunca se reescribe.
7. **Salidas del producto terminado en esta tarea:** ajuste manual (venta directa, merma, corrección de conteo) y
   **descuento automático al marcar un pedido como entregado** (líneas en unidad, porción o docena de recetas finales,
   una sola vez por pedido; si el pedido vuelve atrás, se revierte). Sin salidas el stock solo crecería y no serviría.
8. **Fuera de esta tarea:** que la cotización use primero el producto ya hecho antes de pedir insumos (cambia el
   cálculo de F3 y su `calc_version`; queda como T20 si se valida con una dueña).

## Plan de implementación

### 1. Datos (migración Alembic reversible)
- `recipe.stock_qty` numeric(12,3) default 0 (saldo de producto terminado).
- Tabla `product_movement` (tenant): `recipe_id`, `delta_qty`, `reason` (`production`, `delivery`, `adjustment`,
  `waste`, `void`), `note`, `reference_type`/`reference_id` (producción o pedido), `client_op_id` único por pyme,
  `occurred_at`.
- `production_record`: `consumed_ingredients` bool, `voided_at` timestamptz nullable.
- `pyme.production_consumes_ingredients` bool default true.
- `docs/DATA_MODEL.md` y ADR-011 (producto terminado como existencia, consumo automático, anulación).

### 2. API
- `vision/service.confirm_production`: además del registro, `+confirmed_qty` en `product_movement` y, si corresponde,
  un `stock_movement` `production` negativo por cada línea de la receta (función pura `production_consumption(recipe,
  units, pyme_waste)` sobre `required_qty`). Sube las versiones `production` e `inventory`. La respuesta trae
  `product_stock` y `consumed` (insumo, cantidad, saldo nuevo, `went_negative`).
- `POST /vision/productions/preview` (sin escribir): lo mismo que se va a sumar y descontar, para mostrarlo antes de
  confirmar. Funciona también sin foto (registro manual).
- `POST /vision/productions/{id}/void` (dueña): movimientos inversos, idempotente.
- `GET /vision/productions?recipe_id=&cursor=`: historial (pendiente desde T06).
- Productos terminados en `inventory`: `GET /products/stock` (recetas finales con saldo), `GET
  /products/{recipe_id}/movements`, `POST /products/movements` (ajuste manual: `adjustment` ±, `waste` −; idempotente).
- `quotes`: al pasar un pedido a `delivered`, `delivery` negativo por cada línea contable; al salir de `delivered`, la
  reversa. Una sola vez por pedido (referencia única).
- Fichas del RAG (ADR-006) y consulta del asistente: la ficha de la receta incluye "listas para entregar: N"; nueva
  intención `get_product_stock` ("¿cuántas empanadas tengo listas?") con plantilla de nivel 0.

### 3. PWA
- Pantalla de la foto: antes de "Confirmar", un resumen por producto: "Se suman 48 Empanadas de pino a tus
  existencias" y, plegado, "Se descuentan: harina 1,2 kg, carne 800 g…", con la casilla "Descontar insumos usados".
  Sin red se calcula con las recetas e insumos guardados en el teléfono y se marca como estimado; el servidor aplica el
  cálculo real al sincronizar.
- Inventario: pestañas "Insumos" y "Productos listos". Productos listos muestra el saldo, el historial y un botón de
  ajuste (vendí, se perdió, corregir).
- Historial de producción con "Anular" (dueña).
- Avisos: insumo que quedó negativo; el inicio suma "N productos listos para entregar".
- Textos en `i18n.ts`, cifras con `<Num>`, mobile first.

### 4. Pruebas
- Unitarias: consumo por receta con merma de línea, de insumo y de pyme; redondeo a 3 decimales; receta sin líneas.
- Integración: confirmar → saldo de producto +N y cada insumo −consumo exacto (contra SQL directo); reintento con la
  misma clave no duplica; anular deja todo como antes; casilla apagada no descuenta; insumo negativo avisa; pedido
  entregado descuenta una vez y revertir el estado lo devuelve; aislamiento A/B en todo; colaboradora puede confirmar
  pero no anular.
- PWA: Vitest del resumen previo y de la pestaña de productos; e2e sin red: confirmar sin señal, volver la red y ver el
  stock actualizado una sola vez.

## Entregables
- [x] ADR-011 y `DATA_MODEL.md`
- [x] Migración y modelos
- [x] Confirmación con efecto en inventario, vista previa, anulación e historial
- [x] Productos terminados: saldo, movimientos, ajuste manual y salida al entregar
- [x] Pantallas: resumen antes de confirmar, pestaña "Productos listos", anular
- [x] Asistente: consulta de productos listos (sin ficha del RAG; ver cierre)
- [x] `API.md`, `ARCHITECTURE.md`, índice

## Criterios de aceptación
- Foto de 48 empanadas confirmada → "Empanadas de pino: 48 listas" en inventario y la harina baja exactamente lo que
  dice la receta (verificado contra SQL), en menos de 3 clics desde el resultado del conteo.
- Confirmar sin señal y sincronizar no duplica ni el producto ni los descuentos.
- Anular una producción deja saldos y libro cuadrados (suma de movimientos = saldo).
- Entregar un pedido de 3 docenas descuenta 36 una sola vez.
- `./scripts/check.sh` y la e2e de visión pasan.

## Fuera de alcance
- Que la cotización use el producto terminado antes de comprar insumos (T20 propuesta).
- Vencimiento o lotes de productos terminados, cadena de frío.
- Reentrenar el modelo con fotos reales (sigue en T10, pregunta 6 del índice).

## Riesgos y preguntas abiertas
- Si las recetas están mal cargadas, el descuento automático deja el stock de insumos mal: por eso la vista previa y
  la casilla para no descontar.
- Productos que se venden por peso (pebre, salsas) no se cuentan con foto: quedan con ajuste manual.
- Para validar con una dueña: ¿descuenta al producir (supuesto 3) o prefiere descontar al cotizar o al entregar?

## Resumen de cierre
**Qué se hizo (16-nov-2026):**
- Datos: migración reversible `a350bad426a3` (`product_movement`, `recipe.stock_qty`,
  `production_record.consumed_ingredients`/`voided_at`, `pyme.production_consumes_ingredients`). ADR-011.
- API: `inventory/products.py` (libro de productos con suma atómica, saldo, historial paginado, ajuste y merma
  idempotentes, `sync_order_delivery`); `vision` confirma sumando el producto y descontando insumos en una transacción,
  más vista previa, anulación (solo dueña) e historial; `quotes.update_order` descuenta al entregar sin duplicar;
  ajuste de la pyme en `/pyme`; intención `product_stock` de nivel 0 en el asistente.
- PWA: vista previa "Al confirmar" con casilla "Descontar insumos usados" y aviso de insumo negativo; botón "Ver
  productos listos"; pestañas Insumos / Productos listos con saldo, historial, ajuste y merma por la cola sin red;
  "Producción reciente" con Anular (dueña); casilla en Ajustes.
- Pruebas: 12 en `tests/test_production_stock.py` (consumo exacto contra el libro, reintento sin duplicar, casilla y
  ajuste de la pyme, insumo negativo, conteo 0, anulación idempotente y solo dueña, ajustes y mermas, entrega una vez
  y reversa, aislamiento A/B, asistente sin LLM); Vitest de la vista previa y de "Productos listos"; la e2e de visión
  ahora recorre registro a mano → vista previa → existencias → anular, con axe y sin scroll horizontal a 390 px.

**Decisiones tomadas al implementar:**
- El saldo de productos **no** entra en las fichas del RAG (ADR-006): cambiaría con cada producción y obligaría a
  re-vectorizar la ficha de la receta. Las preguntas de existencias van por la intención `product_stock` (nivel 0).
- Sin señal, la vista previa no muestra números (las líneas de receta y el stock pueden no estar guardados en el
  teléfono): explica que se sumará y descontará según la receta al volver la señal. El servidor aplica el cálculo real.
- Anular está disponible para producciones anteriores a T18; como no movieron stock, solo quedan marcadas como anuladas.
- La e2e de visión ya no depende de que la API de desarrollo no tenga modelo (hoy sí lo tiene): usa "Contar a mano".

**Pendiente:** validar con una dueña cuándo descontar (al producir, supuesto 3); T20 (cotizar usando producto ya
hecho); integrar la rama a `main`.

**Riesgos:** recetas mal cargadas descuentan mal; la vista previa y la casilla lo mitigan.
