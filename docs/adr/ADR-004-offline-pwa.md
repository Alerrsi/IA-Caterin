# ADR-004 — PWA con soporte offline

- Estado: aceptado (9-nov-2026)
- Contexto en: `AGENTS.md` sección 4 (tolerancia a baja conectividad)

## Contexto

Las emprendedoras de La Araucanía trabajan a veces en cocinas, bodegas o eventos rurales con señal móvil débil o intermitente. Si la app deja de funcionar sin red, vuelven a la libreta o a Excel. Pero no todo puede funcionar offline: el LLM, la visión y el cálculo de cotizaciones corren en el servidor.

## Decisión

### Qué funciona sin conexión

| Funciona offline (lectura desde caché) | Se encola y se sincroniza al volver | Requiere conexión |
|----------------------------------------|-------------------------------------|-------------------|
| Lista de insumos con stock (muestra "actualizado hace X") | Movimientos de stock (entrada, salida, ajuste, merma) | Asistente (todos los niveles) |
| Recetas y sus líneas | Registro manual de producción | Extraer un pedido desde texto (LLM) |
| Proveedores y precios vigentes | Borradores de pedido (formulario) | Calcular la cotización y generar el PDF |
| Pedidos próximos | Fotos pendientes de conteo (se infieren al volver) | Conteo por foto (inferencia) |
| Última cotización abierta y su PDF, si ya se descargó | Respuestas de la encuesta | Login inicial, importar CSV/Excel, subir documentos |

### Cómo

1. **App shell en caché** con `vite-plugin-pwa` (Workbox): HTML, JS, CSS, íconos y textos i18n con *precache*. La app abre sin red.
2. **Datos en IndexedDB** (con una capa pequeña tipo `idb` o Dexie): catálogos descargados con `GET ?updated_since=` y revalidados con ETag. Estrategia *stale-while-revalidate*.
3. **Cola de escrituras** en IndexedDB: cada operación lleva un `client_op_id` (UUID) que viaja como `Idempotency-Key`. Se reintenta con *backoff* al volver la red (evento `online` y Background Sync donde exista; en iOS, al abrir la app).
4. **Conflictos:**
   - **Stock:** no hay conflictos porque se envían **movimientos** (deltas), no saldos. Los movimientos se suman en cualquier orden. Si el saldo queda negativo, se avisa pero no se rechaza (la realidad manda).
   - **Catálogos** (insumo, receta, proveedor): *last-write-wins* por `updated_at` del servidor. Si el registro cambió en el servidor después de la versión local, la PWA muestra "este dato cambió, ¿cuál dejo?" en lugar de pisarlo en silencio.
   - **Precios:** no se editan, se crean versiones nuevas, así que no hay conflicto.
5. **Indicadores visibles:** un banner "Sin conexión: tus cambios se guardan y se envían al volver" y un contador de cambios pendientes. Los botones que requieren red se muestran deshabilitados, con una explicación corta.
6. **Fotos offline:** se guardan comprimidas (≤ 1280 px, JPEG ~80%) con un tope configurable de cola (p. ej. 20 fotos o 30 MB) para no llenar el teléfono.
7. **Sesión offline:** el token de acceso vence en 15 minutos, pero la cola se envía al reconectar con un refresh. Si el refresh también venció, se pide login y la cola **se conserva**.

## Alternativas consideradas

- **Offline total con base de datos local sincronizada (CRDT, PouchDB/CouchDB):** demasiado complejo para el MVP y obliga a cambiar el backend.
- **Sin offline:** contradice el principio de accesibilidad y el contexto de la usuaria.
- **Ejecutar el LLM o la visión en el teléfono:** un celular de gama media no corre `qwen3:4b` con una latencia aceptable. RF-DETR Nano en ONNX Web es posible, pero queda para el roadmap.

## Consecuencias

- La API debe soportar `updated_since`, ETag e `Idempotency-Key` desde T04 (no es solo trabajo del frontend).
- El stock se modela como libro de movimientos (`stock_movement`), con el saldo cacheado.
- Las pruebas de T08 incluyen escenarios con la red cortada en Playwright (`context.setOffline(true)`).
- Hay que documentar en la guía de usuaria qué funciona y qué no sin red (T12).
