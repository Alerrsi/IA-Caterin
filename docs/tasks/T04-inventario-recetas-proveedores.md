# T04 — Inventario, recetas, proveedores e importación
- Estado: hecha
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
- [x] CRUD de insumos, proveedores, precios (crear versión nueva) y recetas con sus líneas.
- [x] `POST /stock/movements` idempotente (`Idempotency-Key`), `GET /stock/low`, historial de movimientos.
- [x] `GET /recipes/{id}/cost?qty=` con el desglose por línea, el precio y la fecha usados.
- [x] `GET /ingredients/{id}/prices`: comparación normalizada por unidad base.
- [x] Importación CSV/Excel de insumos y de precios: plantilla descargable, vista previa con errores por fila en español, confirmación y deshacer.
- [x] Soporte de `updated_since` y ETag en el listado de insumos (para la PWA, ADR-004).
- [ ] ETag y `updated_since` en recetas, proveedores y precios → se agregan en T08, cuando la PWA los necesite para el caché offline.
- [x] Incremento de `data_version` por dominio en cada escritura (para la caché del asistente, ADR-005).
- [x] Servicios de **lectura** que usará el asistente: `inventory.get_ingredient`, `inventory.list_low_stock`, `recipes.compute_cost`, `suppliers.compare_prices`, `suppliers.get_supplier`.
- [ ] Si se confirma: registro mínimo de caja (`cash_movement`) y `get_cash_summary` → **no hecho**: sigue pendiente la decisión del equipo (pregunta 3 del índice); la tabla existe.

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
**Qué se hizo (9-nov-2026):**
- Módulos `inventory`, `suppliers`, `recipes` (con `costing.py` puro) e `imports`; helpers `core/http.py` (cursor, ETag, `Idempotency-Key`).
- Precios versionados (un cambio crea una versión nueva; la anterior queda como historial). Comparación normalizada por kg, L o unidad, con IVA.
- Importación sin estado en el servidor: vista previa → confirmar (se revalida) → deshacer. CSV con `;` o `,`, UTF-8 o Latin-1, números chilenos ("21.000", "2,5"); Excel con openpyxl en solo lectura.
- Migración `896f42ac6856`: `ingredient.import_batch_id` e índices de lote.
- **Supuestos** (validar con una emprendedora): el costo usa la presentación vigente **más barata** por unidad base y se expresa **con IVA** (lo que paga la pyme); la importación de insumos **solo crea** (no actualiza stock de insumos existentes); las cantidades se ingresan sin unidad en la unidad base o con unidad explícita.

**Verificado:** 68 pruebas pasan (22 nuevas: costeo puro con Hypothesis, inventario, idempotencia, ETag/304, paginación, proveedores, versionado y comparación de precios, recetas y versión, importación CSV Latin-1 y Excel, deshacer, límites de archivo, aislamiento A/B en todos los endpoints nuevos). El costo de "Empanadas de pino" del seed coincide con la hoja a mano (`tests/fixtures/costo_empanadas_pino.md`: $8.960 por docena, $747 por unidad). Prueba manual con `curl`: 80 empanadas = $59.738. ruff y `mypy --strict` limpios.

**Pendiente / riesgos:**
- Caja (`cash_movement`): pendiente de decisión.
- Formato de importación probado solo con planillas sintéticas; falta una planilla real (anonimizada).
- "Más barato" puede no ser el criterio de la usuaria (proveedor habitual, calidad).
