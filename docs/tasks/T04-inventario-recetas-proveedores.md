# T04 — Inventario, recetas, proveedores e importación
- Estado: pendiente
- Depende de: T03
- Funcionalidad: transversal

## Objetivo
Que la emprendedora deje de llevar el inventario y los costos en Excel: carga sus insumos (a mano o desde su planilla), arma sus recetas y ve al instante cuánto le cuesta producir cada una.

## Contexto y decisiones previas
- Entidades: `docs/DATA_MODEL.md`. Endpoints: `docs/API.md` (inventory, suppliers, recipes).
- Stock = libro de movimientos con saldo cacheado; precios versionados (ADR-004, DATA_MODEL).
- Costeo determinista en `recipes/costing.py` (ADR-002).
- Supuesto: el costo de una receta usa, por cada insumo, el **precio vigente más barato por unidad base** entre los proveedores; si no hay precio, la línea se marca "sin precio" y el total se muestra como incompleto (no se inventa un costo).

## Entregables
- [ ] CRUD de insumos, proveedores, precios (crear versión nueva) y recetas con sus líneas.
- [ ] `POST /stock/movements` idempotente (`Idempotency-Key`), `GET /stock/low`, historial de movimientos.
- [ ] `GET /recipes/{id}/cost?qty=` con el desglose por línea, el precio y la fecha usados.
- [ ] `GET /ingredients/{id}/prices`: comparación normalizada por unidad base.
- [ ] Importación CSV/Excel de insumos y de precios: plantilla descargable, vista previa con errores por fila en español, confirmación y deshacer.
- [ ] Soporte de `updated_since` y ETag en los listados (para la PWA, ADR-004).
- [ ] Incremento de `data_version` por dominio en cada escritura (para la caché del asistente, ADR-005).
- [ ] Servicios de **lectura** que usará el asistente: `get_stock`, `list_low_stock`, `get_recipe_cost`, `compare_prices`, `get_supplier`.
- [ ] Si se confirma: registro mínimo de caja (`cash_movement`) y `get_cash_summary`.

## Criterios de aceptación
- Con los datos del seed, el costo de la receta de empanadas de pino calculado por la API coincide con un cálculo a mano en una hoja (se deja la hoja de verificación en `apps/api/tests/fixtures/`).
- Importar una planilla de 30 insumos con 2 filas erróneas muestra exactamente esas 2 filas con su motivo y permite confirmar las otras 28.
- Enviar dos veces el mismo movimiento con la misma `Idempotency-Key` deja un solo movimiento.
- Aislamiento A/B en todos los endpoints nuevos.

## Pruebas requeridas
- Unitarias: costeo (merma, rendimiento, unidades mixtas, línea sin precio), normalización de precio por unidad base, parser de importación (separador `;` y `,`, coma decimal chilena "2,5", miles con punto "21.000").
- Integración: endpoints, idempotencia, ETag/304, aislamiento.

## Fuera de alcance
- Sub-recetas, fuentes de precios automáticas (`PriceSource` con scraping), interfaz (T08).

## Riesgos y preguntas abiertas
- Las planillas reales pueden ser muy distintas entre sí; conseguir 1 o 2 ejemplos reales (anonimizados) antes de cerrar el formato de importación.
- ¿"Más barato por unidad base" es el criterio correcto para el costo? Tal vez la usuaria prefiere su proveedor habitual. Validar.

## Resumen de cierre
(se completa al terminar)
