# T17 — Tablero del negocio con gráficos (solo dueña)
- Estado: hecha en la rama (16-nov-2026); falta integrar a `main`
- Rama: `feat/T17-tablero`
- Depende de: T04 (inventario), T05 (cotizaciones), T09 (métricas), T16 (estética)
- Funcionalidad: transversal

## Objetivo
Que la dueña vea en una sola pantalla cómo va su negocio: cuánto vendió por mes, cuánto le quedó después de pagar
los insumos, qué productos se piden más, qué eventos vienen, a qué proveedores les compra y qué insumos se están
acabando. Así no tiene que armar una planilla para saberlo.

## Contexto y decisiones previas
- Pedido del usuario (16-nov-2026): "define un plan de implementación y luego desarróllalo; debe mostrarse para el
  dueño de la pyme". Antes de esto no había gráficos en la app: `/metricas` (T09) muestra cifras y una tabla.
- `/metricas` sigue igual: mide si Cáterin ahorra tiempo (métricas del proyecto). El tablero mide el **negocio**.
- Principio 4 de AGENTS.md: todas las cifras salen de código determinista (`Decimal`, CLP sin decimales). El LLM no
  participa.
- Multi-tenant: la sesión de tenant filtra por `pyme_id` (RLS, ADR-006-rls). Hay una prueba A/B.

### Supuestos (decididos sin preguntar; ver memoria "decidir detalles sin preguntar")
1. **Venta = cotización aceptada.** Un pedido confirmado o entregado cuenta como venta con su última cotización
   aceptada (mayor `version` con `status = accepted`). Un pedido sin cotización aceptada se cuenta como pedido, pero
   no suma dinero, y se informa cuántos hay.
2. **El mes de la venta es el mes del evento** (`event_date`; si falta, la fecha de creación del pedido), en
   America/Santiago. El mes en curso incluye los eventos confirmados que aún no ocurren, y la pantalla lo dice.
3. **Margen sobre insumos = venta neta (sin IVA) − costo de insumos de la cotización.** No es la utilidad: no incluye
   sueldos, arriendo ni gas, y la pantalla lo aclara.
4. **Caja (`cash_movement`) queda fuera.** Su entrada al MVP sigue abierta (pregunta 3 del índice) y no hay pantalla
   para registrar movimientos, así que una pyme real vería el gráfico vacío.
5. **Productos más pedidos en unidades:** unidad y porción cuentan 1, docena 12. Las líneas en g, kg, ml o L no se
   suman a las unidades (se informa cuántas quedaron fuera).
6. **Compras por proveedor = estimación:** suma de `subtotal_clp` de las líneas de las cotizaciones aceptadas del
   periodo. No son compras reales registradas.
7. **Gráficos en SVG propio, sin librería.** Son barras simples. Así no se agregan ~100 KB al paquete de la PWA ni una
   dependencia nueva (AGENTS.md 5), y funcionan sin red.
8. **Colores de los gráficos:** dos tonos nuevos fuera del bloque generado del tema, `--color-chart-1` `#14845c`
   (laurel más saturado) y `--color-chart-2` `#d4874c` (cobre claro). Se validaron con
   `validate_palette.js` de la skill `dataviz`: banda de luminosidad, croma, separación para daltonismo (ΔE 8,5 en
   protanopía) y visión normal (ΔE 23,8) pasan. El cobre queda bajo 3:1 contra blanco (2,85:1): por eso cada
   gráfico tiene etiquetas de texto y una vista en tabla. El cobre es un color de dato, no un acento de interfaz.
   Los insumos bajo el mínimo usan los colores de estado de aviso, siempre con ícono y texto.
9. **Periodo:** selector de 3, 6 o 12 meses (por defecto 6), que termina en el mes en curso.
10. **Sin red:** la respuesta se guarda en el teléfono (`useCached`, ADR-004) y se muestra la fecha del dato.

## Plan de implementación

### API (`apps/api/app/modules/dashboard`)
`GET /api/v1/dashboard?months=6` (1 a 12; solo dueña; colaboradora 403). Una sola respuesta, pequeña:

| Bloque | Contenido |
|--------|-----------|
| `period` | `date_from`, `date_to`, `months`, `today`, zona horaria |
| `kpis` | venta total con IVA, venta neta, margen sobre insumos (CLP y %), pedidos vendidos, ticket promedio, pedidos sin cotización aceptada, solicitudes del portal por responder, eventos de los próximos 7 días, insumos bajo el mínimo |
| `sales_by_month` | por mes: pedidos, venta neta, costo de insumos, margen, venta con IVA (todos los meses, aunque estén en cero) |
| `orders_by_status` | pedidos del periodo por estado (sin los borradores del portal, que la pyme no ve) |
| `top_products` | hasta 8 productos por unidades pedidas, con cuántos pedidos y cuántas líneas quedaron fuera por unidad de peso o volumen |
| `upcoming_by_day` | los próximos 14 días: pedidos confirmados y por confirmar, e invitados |
| `spend_by_supplier` | hasta 5 proveedores por compra estimada, más "Otros" |
| `low_stock` | hasta 8 insumos bajo el mínimo, ordenados por qué tan cerca de cero están, más el total |

Archivos: `schemas.py`, `service.py` (consultas + agregación pura en `Decimal`), `router.py`, registro en `main.py`.

### Web (`apps/web`)
- `src/components/charts.tsx`: `StatTile`, `ColumnChart` (columnas apiladas con eje Y, rejilla fina, tooltip al
  pasar el mouse, tocar o enfocar con teclado), `BarList` (barras horizontales con el valor en la punta),
  `Meter` (stock contra mínimo), `Legend` y `TableView` (`<details>` con la tabla de cada gráfico).
- `src/pages/Dashboard.tsx` en `/tablero`: filtro de periodo arriba, fila de cifras, luego venta por mes (insumos +
  margen), próximos 14 días, productos más pedidos, pedidos por estado, compras por proveedor e insumos por acabarse
  (cada fila lleva al insumo).
- Acceso: celda "Mi negocio" en el inicio (solo dueña), entrada en la navegación de la dueña y ruta protegida. La
  colaboradora ve el aviso "solo la dueña".
- Textos en `i18n.ts` (es-CL), formatos con `format.ts` (CLP compacto en el eje: `$1,2 M`).

### Pruebas
- API: agregación pura (meses en cero, margen, ticket con redondeo, unidades por docena, "Otros"), endpoint con
  datos creados por la API, colaboradora 403, aislamiento entre dos pymes, cifra de venta contra SQL directo.
- Web: Vitest de la página (dueña ve gráficos y tabla; colaboradora ve el aviso; vacío), escalas y formato compacto.
- Visual: captura a 390 y 1280 px con los datos de demo (`demo_full`).

## Entregables
- [x] Plan (este documento)
- [x] Módulo `dashboard` en la API con pruebas
- [x] Componentes de gráficos y página `/tablero`
- [x] Acceso desde inicio y navegación, solo dueña
- [x] `docs/API.md`, `docs/ARCHITECTURE.md` e índice actualizados

## Criterios de aceptación
- `GET /api/v1/dashboard` responde 200 a la dueña, 403 a la colaboradora y nunca mezcla datos de otra pyme.
- La venta del mes del tablero coincide con una consulta SQL directa sobre `quote` y `catering_order`.
- `/tablero` se lee a 390 px sin scroll horizontal; cada gráfico tiene leyenda (si tiene 2 series), tooltip y tabla.
- `npm test`, `npm run typecheck`, `npm run lint`, `pytest`, `ruff` y `mypy` pasan.

## Fuera de alcance
- Caja (ingresos y gastos reales), utilidad neta, proyecciones, exportar el tablero a PDF.
- Gráficos para la colaboradora o para el cliente del portal.

## Riesgos y preguntas abiertas
- Con pocos pedidos los gráficos pueden sugerir tendencias que no existen: se muestra el número de pedidos de cada mes.
- Si el equipo decide que la venta se cuenta al aceptar la cotización (y no por fecha del evento), cambia el mes de
  algunas ventas. Es un cambio de una línea en `service.py`.

## Resumen de cierre
**Qué se hizo (16-nov-2026):**
- API `GET /api/v1/dashboard` (`app/modules/dashboard`): consultas de solo lectura con la sesión de tenant y agregación
  pura en `Decimal`. 10 pruebas en `tests/test_dashboard.py`: unitarias (meses en cero, margen, ticket con redondeo,
  docenas, «Otros», cruce de año), venta del mes contra SQL directo, dueña 200 / colaboradora 403 / sin sesión 401 /
  `months` fuera de rango 422, y aislamiento con una segunda pyme. Cobertura del servicio: 99 %.
- Web: `components/charts.tsx` (columnas apiladas en SVG con eje, rejilla, tooltip con mouse, toque y teclado; barras
  horizontales; medidor de stock; tabla plegable; cifras destacadas) y `pages/Dashboard.tsx` en `/tablero`, con
  acceso "Mi negocio" en el inicio y en la navegación, solo para la dueña. Guarda el último dato para verlo sin red.
- Pruebas web: `Dashboard.test.tsx` (4) y `e2e/dashboard.e2e.ts` (axe sin violaciones serias, sin scroll horizontal a
  390 y 1280 px, también al volver de 1280 a 390, y tooltip al tocar). Capturas en `apps/web/e2e-artifacts/tablero/`
  (no se versionan).
- `./scripts/check.sh` completo pasa: ruff, mypy, pytest (cobertura total 96 %), eslint, tsc y Vitest (148).

**Medido con la demo grande (Banquetería Volcán Llaima, datos sintéticos), 6 meses:** venta con IVA $20.769.630,
104 pedidos vendidos, margen sobre insumos 31 %. Son datos de demo, no de una pyme real.

**Pendiente:**
- Mostrarlo a una dueña real y validar si la venta debe contarse por fecha del evento o por fecha de aceptación.
- Caja real (ingresos y gastos) cuando el equipo decida la pregunta 3 del índice.
- Integrar la rama a `main` cuando el usuario lo apruebe.

**Riesgos:** con pocos pedidos por mes las barras exageran variaciones; el tooltip y la tabla muestran cuántos pedidos
hay detrás de cada mes.
