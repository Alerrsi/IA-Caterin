# API — Cáterin

- Estado: diseño inicial (9-nov-2026). La fuente de verdad será el OpenAPI generado por FastAPI en `/api/v1/openapi.json` (con interfaz en `/docs`). Este documento resume y se mantiene al día con cada tarea.
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
| PATCH/DELETE | `/users/{id}` | Cambiar rol o desactivar — solo dueña |

### inventory (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/ingredients` | Listar (con stock) y crear insumos |
| GET/PATCH/DELETE | `/ingredients/{id}` | Detalle, editar y desactivar |
| GET | `/ingredients/{id}/movements` | Historial de movimientos |
| POST | `/stock/movements` | Registrar entrada, salida, ajuste o merma (idempotente) |
| GET | `/stock/low` | Insumos bajo el mínimo |
| POST | `/imports/ingredients` | Subir CSV o Excel → **vista previa** con errores por fila |
| POST | `/imports/{import_id}/confirm` | Confirmar la importación |
| DELETE | `/imports/{import_id}` | Deshacer una importación confirmada (si no se usó) |

### suppliers (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/suppliers` | Listar y crear proveedores |
| GET/PATCH/DELETE | `/suppliers/{id}` | |
| GET/POST | `/prices` | Listar precios vigentes (filtro por insumo o proveedor) y crear un precio nuevo (versiona el anterior) |
| GET | `/ingredients/{id}/prices` | Comparación de precios vigentes de un insumo, normalizados por unidad base |
| POST | `/imports/prices` | Importar una lista de precios (CSV/Excel) con vista previa |

### recipes (T04)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET/POST | `/recipes` | Listar y crear recetas con sus líneas |
| GET/PATCH/DELETE | `/recipes/{id}` | |
| GET | `/recipes/{id}/cost?qty=` | Costo calculado para N unidades, con el desglose y los precios usados |

### quotes (T05)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/orders/extract` | Texto libre → pedido interpretado (borrador editable). Un reintento si el JSON no valida; si vuelve a fallar responde `extraction_failed` y la PWA abre el formulario |
| GET/POST | `/orders` | Listar y crear pedidos (desde el formulario o desde el borrador confirmado) |
| GET/PATCH | `/orders/{id}` | |
| POST | `/orders/{id}/quotes` | Calcular una cotización nueva (insumos, stock, compras, comparación, totales) |
| GET | `/quotes/{id}` | Detalle con líneas, supuestos y precios usados |
| GET | `/quotes/{id}/shopping-list` | Lista de compras agrupada por proveedor |
| GET | `/quotes/{id}/pdf` | PDF para el cliente final (`application/pdf`) |
| PATCH | `/quotes/{id}` | Cambiar el estado (enviada, aceptada, rechazada) |

### vision (T06)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/vision/count` | Multipart `image` (JPEG/PNG/WebP, ≤ 8 MB) → conteo por producto, cajas, versión del modelo y latencia |
| POST | `/vision/productions` | Confirmar el conteo corregido → `production_record` (idempotente) |
| GET | `/vision/productions` | Historial |
| GET | `/vision/model` | Versión y clases del modelo cargado |

### assistant (T07)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/assistant/ask` | `{ "question": "...", "quick_action": null }`. Responde en SSE (`text/event-stream`): eventos `meta` (nivel, intención, fuentes), `token`, `final` (texto completo, fuentes, latencia) y `error`. Con `Accept: application/json` responde en un bloque |
| GET | `/assistant/quick-actions` | Botones de preguntas frecuentes (van directo al nivel 0) |
| POST | `/assistant/feedback` | Pulgar arriba/abajo sobre una respuesta |
| GET/POST | `/documents` | Listar y subir documentos (PDF, XLSX, CSV, TXT, ≤ 10 MB) para el nivel 2 |
| DELETE | `/documents/{id}` | Borra el documento y sus fragmentos |

### metrics (T09)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/metrics/survey` | Encuesta de 1 a 5 estrellas (+ comentario opcional) |
| POST | `/metrics/quote-timing` | Tiempo de una cotización (inicio y fin medidos en la PWA) |
| POST | `/metrics/manual-baseline` | Registro del tiempo de una cotización manual de referencia |
| GET | `/metrics/summary` | Panel: satisfacción, tiempo de cotización antes/después, latencia por nivel, % de consultas sin LLM — solo dueña |

## 5. Convenciones

- Rutas en inglés, en plural y en kebab-case. Los campos JSON en `snake_case`.
- Dinero como **entero en CLP** en JSON (`"total_clp": 125000`). Cantidades como **string decimal** (`"qty": "2.500"`) para no perder precisión en JavaScript.
- Fechas en ISO 8601. `date` para fechas de evento y de precio; `datetime` en UTC con `Z`.
- Versionado: cambios incompatibles → `/api/v2`. En `/api/v1` solo se agregan campos opcionales.
