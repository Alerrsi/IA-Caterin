# API — Cáterin

- Estado: implementados auth (T03), inventario, proveedores, recetas e importación (T04), pedidos y cotizaciones (T05) y métricas (T09). El resto es diseño. La fuente de verdad será el OpenAPI generado por FastAPI en `/api/v1/openapi.json` (con interfaz en `/docs`). Este documento resume y se mantiene al día con cada tarea.
- Base: `https://<dominio>/api/v1`. Todo es JSON (UTF-8) salvo la carga de archivos (multipart), los PDF y el *streaming* del asistente (SSE).

## 1. Autenticación y roles

- **JWT de acceso** de corta duración (15 min, configurable) en `Authorization: Bearer <token>`.
- **Refresh token** de larga duración (30 días, configurable) en una cookie `HttpOnly`, `Secure`, `SameSite=Strict`, rotado en cada uso.
- El token lleva `sub` (usuario), `pyme_id` y `role`. El `pyme_id` **solo** se toma del token (ver DATA_MODEL, multi-tenancy).

| Acción | Dueña (`owner`) | Colaboradora (`collaborator`) |
|--------|:---------------:|:-----------------------------:|
| Ver inventario, recetas, pedidos | ✔ | ✔ |
| Ajustar stock, registrar producción | ✔ | ✔ |
| Crear y editar recetas, proveedores, precios | ✔ | ✔ (a confirmar con el equipo) |
| Ver costos, márgenes y caja | ✔ | ✘ (propuesta) |
| Generar y enviar cotizaciones | ✔ | ✘ (propuesta) |
| Invitar usuarias, configurar la pyme | ✔ | ✘ |
| Usar el asistente | ✔ | ✔ (solo intenciones permitidas a su rol) |

## 2. Errores (RFC 9457)

Todas las respuestas de error usan `application/problem+json`:

```json
{
  "type": "urn:caterin:problem:ingredient_not_found",
  "title": "No encontramos ese insumo",
  "status": 404,
  "detail": "El insumo que buscas no existe o fue eliminado.",
  "instance": "/api/v1/ingredients/0193…",
  "code": "ingredient_not_found",
  "request_id": "a1b2c3"
}
```

- `title` y `detail` en español de Chile, en lenguaje simple. `code` es estable para el frontend.
- Errores de validación (422): se agrega `errors: [{ "field": "qty", "message": "Debe ser mayor que cero" }]`.
- Nunca se incluyen trazas, SQL ni datos de otra pyme.

## 3. Paginación, caché y escrituras offline

- **Paginación por cursor:** `?limit=20&cursor=<opaco>`. El valor por defecto es 20 y el máximo 100. La respuesta es `{ "items": [...], "next_cursor": "..." | null }`.
- **Filtros simples:** `?q=` (búsqueda por nombre), `?updated_since=` (para sincronizar la PWA).
- **ETag / If-None-Match** en los catálogos (insumos, recetas, proveedores, precios), para que la PWA revalide con un 304 y gaste pocos datos.
- **`Idempotency-Key`** (UUID) obligatorio en los POST que la PWA puede encolar sin red. Si se repite la clave, se devuelve la respuesta original sin duplicar (ver ADR-004).
- Respuestas pequeñas: los listados devuelven campos resumidos; el detalle va en `GET /{id}`.

## 4. Endpoints por módulo

### Salud
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health/live` | Proceso vivo |
| GET | `/health/ready` | Base de datos, Ollama y modelo ONNX disponibles (detalle por componente) |

### auth (T03)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/register` | Crea la pyme y su dueña |
| POST | `/auth/login` | Correo y contraseña → token de acceso (+ cookie de refresh) |
| POST | `/auth/refresh` | Rota el refresh y entrega un nuevo token de acceso |
| POST | `/auth/logout` | Revoca el refresh |
| GET | `/auth/me` | Usuaria y pyme actuales |
| GET/PATCH | `/pyme` | Ver y editar la configuración (merma, margen, IVA) — solo dueña |
| GET/POST | `/users` | Listar e invitar colaboradoras — solo dueña |
| PATCH/DELETE | `/users/{id}` | Cambiar nombre, rol, contraseña o desactivar (DELETE desactiva, no borra) — solo dueña. Protege a la última dueña activa |

### inventory (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/ingredients` | Listar (con stock) y crear insumos |
| GET/PATCH/DELETE | `/ingredients/{id}` | Detalle, editar y desactivar |
| GET | `/ingredients/{id}/movements` | Historial de movimientos |
| POST | `/stock/movements` | Registrar entrada, salida, ajuste o merma (idempotente) |
| GET | `/stock/low` | Insumos bajo el mínimo |
| GET | `/ingredients?q=&limit=&cursor=&updated_since=&low_only=` | Paginado por cursor, con ETag |
| GET | `/imports/templates/{ingredients\|prices}.csv` | Plantilla de ejemplo (separador `;`) |
| POST | `/imports/ingredients/preview` | Subir CSV o Excel (multipart `file`) → filas válidas ya normalizadas + errores por fila. No guarda nada |
| POST | `/imports/ingredients/confirm` | Reenviar las filas válidas (`{"rows": [...]}`); se validan de nuevo y se crean con un `import_batch_id`. Solo crea insumos nuevos |
| DELETE | `/imports/{import_batch_id}` | Deshacer una importación (insumos o precios) si sus datos no se usaron; con precios, vuelve a la versión anterior |

### suppliers (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/suppliers` | Listar y crear proveedores |
| GET/PATCH/DELETE | `/suppliers/{id}` | |
| GET/POST | `/prices` | Listar precios vigentes (filtro por insumo o proveedor) y crear un precio nuevo (versiona el anterior) |
| GET | `/ingredients/{id}/prices` | Comparación de precios vigentes de un insumo, normalizados por unidad base |
| POST | `/imports/prices/preview` | Lista de precios (CSV/Excel) → vista previa; marca los proveedores nuevos |
| POST | `/imports/prices/confirm` | Crea los precios (y los proveedores que falten) |

### recipes (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/recipes` | Listar y crear recetas con sus líneas |
| GET/PATCH/DELETE | `/recipes/{id}` | |
| GET | `/recipes/{id}/cost?qty=` | Costo calculado para N unidades, con IVA, usando por insumo la presentación vigente más barata; desglose por línea, precios usados y `is_complete` si falta algún precio |

### quotes (T05)
| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| POST | `/orders/extract` | ambas | `{"text": "..."}` → pedido interpretado como tabla editable (productos con receta sugerida, cantidad, unidad, invitados, fecha). **No guarda nada.** Un reintento si el JSON del LLM no valida; si vuelve a fallar → 422 `extraction_failed`; sin LLM → 503 `llm_unavailable`. En ambos casos la interfaz ofrece el formulario |
| GET | `/orders?status=&upcoming_days=` | ambas | Pedidos, por fecha de evento |
| POST | `/orders` | ambas | Crear pedido (desde el formulario o desde lo extraído y confirmado). Cada línea exige `recipe_id` |
| GET/PATCH | `/orders/{id}` | ambas | Ver y editar (las líneas se reemplazan completas) |
| POST | `/orders/{id}/quotes` | dueña | `{"margin_pct"?, "use_stock"?, "started_at"?}` → cotización nueva (versión siguiente). 422 `margin_required` si no hay margen; 422 `quote_calculation` si una unidad no calza con la receta |
| GET | `/orders/{id}/quotes` | dueña | Versiones de la cotización |
| GET | `/quotes/{id}` | dueña | Detalle: productos con precio, insumos (necesario, stock usado, a comprar, presentación elegida y alternativas), totales, supuestos |
| PATCH | `/quotes/{id}` | dueña | Cambiar estado. `sent`/`accepted` exigen cotización completa; `accepted` confirma el pedido |
| GET | `/quotes/{id}/shopping-list` | dueña | Lista de compras agrupada por proveedor, con días de despacho |
| GET | `/quotes/{id}/pdf` | dueña | PDF para el cliente final (productos, precios, neto, IVA, total; **sin costos internos**). 409 `quote_incomplete` si falta algún precio |

### vision (T06)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/vision/count` | Multipart `image` (cualquier formato que lea Pillow, ≤ 15 MB; no se guarda) → `counts` por clase unidos a la receta que declara esa `vision_class` (`recipe_id` nulo si ninguna), `detections` (cajas normalizadas), `model_version` y `elapsed_ms`. 415 `invalid_image`, 413 `image_too_large`, 503 `vision_model_unavailable` si no hay modelo (la interfaz ofrece contar a mano) |
| POST | `/vision/productions` | `{recipe_id, confirmed_qty, detected_qty?, model_version?, detections?}` → `production_record`; `was_corrected` si lo confirmado difiere de lo detectado. Con `Idempotency-Key`, un reintento devuelve el original (200, `replayed: true`). 404 si la receta no existe o no es producto final |
| GET | `/vision/model` | `{loaded, version, classes, input_size, sha256}` del modelo cargado; `loaded: false` si no hay |

El historial de producciones (`GET /vision/productions`) queda pendiente. El modelo se carga al iniciar desde `VISION_MODEL_PATH` (`model.onnx` + `model.json`).

### assistant (T07)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/assistant/ask` | `{ "question": "...", "quick_action": null }` → `{answer, level, intent, status, sources, options, fallback_reason, cache_hit, latency_ms, interaction_id}`. Con `Accept: text/event-stream` responde en *streaming* (SSE, abajo) |
| GET | `/assistant/quick-actions` | Botones de preguntas frecuentes; se envían como `quick_action` y entran directo al nivel 0 |
| POST | `/assistant/feedback` | `{interaction_id, useful: true\|false}` → 204. 404 `interaction_not_found` si no existe o es de otra pyme |

- `level`: **0** = plantilla con datos reales, sin LLM; **1** = el LLM redactó con el dato ya resuelto (solo con `ASSISTANT_USE_LLM=true` y si la intención lo permite); **2** = desde los documentos subidos: el fragmento citado tal cual o, con el LLM encendido, un resumen que cita (`sources` trae archivo, página, hoja o filas).
- `status`: `ok`, `no_data`, `ambiguous` (hay `options` para elegir), `missing_entity` o `unrecognized` (`options` = intenciones probables).
- `fallback_reason`: `figures_mismatch` (el LLM puso una cifra que no está en el dato), `llm_unavailable`, `llm_timeout`, `llm_invalid` (respuesta vacía) o `no_intent`. En todos los casos se entrega la respuesta determinista.
- Intenciones: stock de un insumo, qué me falta, costo de una receta, pedidos próximos, qué lleva un pedido, si alcanza el stock para un pedido, mejor precio, datos de un proveedor y producción registrada. Falta "¿cómo va la caja?" (pregunta abierta 3 del índice).
- El nivel 2 se usa cuando la pregunta no calza con ninguna intención y hay fragmentos que coinciden; no se cachea.

**SSE** (`Accept: text/event-stream`). Los errores (401, 404, 422) se responden antes de abrir el stream, como JSON *problem details*. Eventos, en orden:

| Evento | `data` | Qué hace la interfaz |
|--------|--------|----------------------|
| `meta` | `{intent, status, drafting, sources, options, cache_hit}` | Muestra fuentes y botones de inmediato; `drafting: true` = viene texto del LLM |
| `delta` | `{text}` | Agrega el texto. Llega por palabras completas y **cada cifra ya está verificada** |
| `replace` | `{text, fallback_reason}` | El texto del LLM se descartó: reemplazar todo lo mostrado por `text` (la plantilla) |
| `done` | Igual que la respuesta JSON | Respuesta final; trae `interaction_id` para el feedback |

### documents (T07, nivel 2 del asistente)
| Método | Ruta | Rol | Descripción |
|--------|------|-----|-------------|
| GET | `/documents` | ambas | Documentos de la pyme: `{id, filename, mime_type, size_bytes, index_status, chunks, has_embeddings, created_at}` |
| POST | `/documents` | dueña | Multipart `file`: PDF, Excel (`.xlsx`), CSV, TXT o MD (≤ `DOCUMENT_MAX_UPLOAD_MB`, 10 MB). Se fragmenta (por página, hoja o grupo de filas) y se indexa. Si los embeddings no responden, queda buscable solo por texto (`has_embeddings: false`). 409 `document_exists` (mismo archivo), 413 `file_too_large`, 415 `unsupported_document`, 422 `unreadable_document` o `empty_document` |
| DELETE | `/documents/{id}` | dueña | Borra el documento, sus fragmentos y el archivo |

### metrics (T09)
| Método | Ruta | Quién | Descripción |
|--------|------|-------|-------------|
| POST | `/metrics/survey` | Cualquiera | `{ "stars": 1..5, "comment": null, "context": "general" \| "quote" \| "assistant" \| "vision" }` |
| POST | `/metrics/quote-timing` | Cualquiera | `{ "started_at", "ended_at", "quote_id", "source" }` medidos en la PWA (con zona horaria). Máximo 24 h. Con `quote_id` es idempotente: si esa cotización ya tiene tiempo responde **200** con el registro existente; si la cotización es de otra pyme, 404 |
| POST | `/metrics/manual-baseline` | Dueña | `{ "task": "quote" \| "data_lookup", "seconds", "reference", "repetition", "measured_on", "tool", "notes" }`. Protocolo: `docs/metrics/protocolo-cotizacion-manual.md` |
| GET | `/metrics/summary?from=&to=` | Dueña | Satisfacción (promedio, n, distribución), mediana del tiempo de cotización con Cáterin y a mano, mediana de buscar un dato (asistente y a mano), latencia p50/p95 por nivel, % sin LLM (nivel 0), % de degradaciones (`fallback_reason`), periodo, `low_n` en cada cifra (n < 5) y `warnings` |
| GET | `/metrics/summary.csv?from=&to=` | Dueña | El mismo resumen en CSV (`;`, coma decimal, UTF-8 con BOM) para Excel |

- `from` y `to` son días en `America/Santiago`, ambos incluidos; por defecto, desde el inicio hasta hoy. Las mediciones manuales no se filtran por periodo (son la línea base).
- Percentiles con interpolación lineal, igual que `percentile_cont` de Postgres. Sin datos, el valor es `null` (nunca 0).
- La PWA ya no manda `started_at` al crear la cotización: usa `/metrics/quote-timing`. El campo `started_at` de `POST /orders/{id}/quotes` se mantiene por compatibilidad y comparte la misma regla de un registro por cotización.

## 5. Convenciones

- Rutas en inglés, en plural y en kebab-case. Los campos JSON en `snake_case`.
- Dinero como **entero en CLP** en JSON (`"total_clp": 125000`). Cantidades como **string decimal** (`"qty": "2.500"`) para no perder precisión en JavaScript.
- Fechas en ISO 8601. `date` para fechas de evento y de precio; `datetime` en UTC con `Z`.
- Versionado: cambios incompatibles → `/api/v2`. En `/api/v1` solo se agregan campos opcionales.
