# ADR-005 — Asistente por niveles: determinista primero, LLM al final

- Estado: aceptado en el diseño (9-nov-2026). El umbral del enrutador y los presupuestos de latencia quedan **a calibrar** en T10.
- Contexto en: `AGENTS.md` principio 5, sección 4 (F1) y sección 3.1

## Contexto

La forma "estándar" de hacer un asistente con datos es un agente: el LLM lee la pregunta, elige herramientas, las llama y redacta. El benchmark propio en CPU (i5-8250U, sin GPU) muestra que eso no sirve aquí:

| Hallazgo medido | Consecuencia |
|-----------------|--------------|
| `qwen3:4b` acertó **1/4** en tool calling (falló los tres casos que necesitaban una herramienta) | El modelo chico no puede decidir qué consulta hacer |
| `qwen3:8b` acertó 4/4, pero a 4.3 tokens/s y con p95 de 25.2 s **en una sola llamada** | Un agente necesita al menos 2 llamadas (estimación): > 30 s por respuesta, inaceptable |
| `bge-m3` responde una consulta de embedding en 156 ms p50 | Reconocer intenciones por similitud es barato |
| `qwen3:4b` genera a 7.5 tokens/s con prefill de 1.2 s | Redactar unos 80 tokens toma ~11 s (estimación): aceptable solo con *streaming* y solo cuando aporta |

Además, las preguntas de una pyme de catering son pocas y repetitivas: ¿cuánto me queda de X?, ¿cuánto me cuesta esta receta?, ¿qué pedidos tengo?, ¿cómo va la caja? Para eso no hace falta un LLM.

## Decisión

### Niveles

| Nivel | Cuándo | Cómo | LLM | Presupuesto (propuesta, a validar) |
|-------|--------|------|-----|------------------------------------|
| 0 | Intención clara y datos resueltos | Enrutador → consulta tipada → plantilla | Ninguno | p95 ≤ 1.5 s |
| 1 | Resumen, comparación o explicación breve | Igual que el 0, más una redacción del LLM con el dato compacto | 1 llamada, *streaming* | Primer texto ≤ 3 s, completa p95 ≤ 15 s |
| 2 | Pregunta abierta sobre documentos subidos | Búsqueda híbrida → 3 a 5 fragmentos → LLM redacta y cita | 1 llamada, *streaming* | Igual que el 1 |
| 3 | Preguntas que cruzan varias consultas | Agente con herramientas de solo lectura | Varias | **Apagado por defecto**; requiere GPU o proveedor externo |

### Enrutamiento (sin LLM)

1. **Botones rápidos** → nivel 0 directo.
2. **Reglas y palabras clave** (regex sobre texto normalizado sin tildes) para lo obvio: "cuánto me queda", "stock de", "qué pedidos", "cuánto cuesta la receta".
3. **Similitud con embeddings**: coseno entre la pregunta y los ejemplos de cada intención (`bge-m3`). Se usa el máximo por intención y se exige un margen frente a la segunda.
4. **Umbral:** se calibra en T10 con el set dorado, maximizando aciertos con una tasa de enrutamiento erróneo ≤ 5% (propuesta). **Mientras no se calibre**, se usa un valor provisional configurable (`ASSISTANT_ROUTER_THRESHOLD`), que **no está medido** y se documenta como tal.
5. Bajo el umbral: si hay documentos con coincidencias en la búsqueda híbrida, nivel 2; si no, una pregunta de aclaración con 2 o 3 intenciones probables como botones; si nada aplica, "no tengo ese dato".

### Resolución de entidades (en código)

- Insumos, recetas y proveedores: `rapidfuzz` (`token_set_ratio` sobre nombres normalizados) contra el catálogo de la pyme. Con varias opciones cercanas, se le pregunta a la usuaria.
- Fechas en español de Chile: "hoy", "mañana", "pasado mañana", "esta semana", "el sábado", "el 22", "fin de mes". Zona horaria `America/Santiago`.
- El LLM **nunca** resuelve entidades.

### Catálogo inicial de intenciones (`apps/api/app/modules/assistant/intents.yaml`)

| Intención | Consulta | Ejemplos | Nivel 1 |
|-----------|----------|----------|:-------:|
| `stock_of_item` | `get_stock(item)` | "¿cuánta harina me queda?", "¿tengo crema?" | no |
| `low_stock` | `list_low_stock()` | "¿qué me falta?", "¿qué tengo que comprar?" | sí |
| `recipe_cost` | `get_recipe_cost(recipe, qty)` | "¿cuánto me sale la docena de empanadas?" | sí |
| `upcoming_orders` | `list_upcoming_orders(range)` | "¿qué pedidos tengo esta semana?" | sí |
| `order_detail` | `get_order(order)` | "¿qué lleva el pedido del sábado?" | no |
| `order_feasibility` | `check_order_stock(order)` | "¿me alcanza para el pedido del sábado?" | sí |
| `best_price` | `compare_prices(item)` | "¿dónde está más barata la harina?" | sí |
| `supplier_info` | `get_supplier(supplier)` | "¿qué días despacha Molino Sur?" | no |
| `cash_summary` | `get_cash_summary(range)` | "¿cómo va la caja este mes?" | sí |
| `production_summary` | `get_production(range)` | "¿cuántas empanadas hice hoy?" | no |

Formato de cada entrada: `name`, `examples` (≥ 8 frases variadas, con chilenismos y errores de tipeo comunes), `keywords`, `query`, `params`, `template`, `allow_level1`, `roles`. El archivo está versionado y su versión se guarda en cada `assistant_interaction`.

Los ejemplos de frases se escriben con el equipo y, si se puede, con frases reales de emprendedoras. No se inventan datos de negocio en las plantillas.

### Caché

- Clave: `(pyme_id, intent, entities_normalized, data_version[dominios de la intención], template_version, level)`.
- `data_version` se incrementa en la misma transacción que cada escritura relevante (DATA_MODEL), así que la invalidación es inmediata y no depende de un TTL.
- Almacenamiento: LRU en memoria del proceso de la API (el MVP tiene una sola instancia). Si se escala a varias instancias, se pasa a una tabla de Postgres o a Redis con un ADR.
- Se cachean el nivel 0 y el 1. El nivel 2 no se cachea en el MVP.

### Llamada al LLM (niveles 1 y 2)

- Un solo llamado por consulta, en *streaming*, con `num_predict` ≈ 120 e instrucción de responder en 2 o 3 frases.
- Contexto: prefijo fijo (sistema y formato) más el dato compacto (JSON mínimo o tabla corta), nunca el inventario completo.
- **Timeout** configurable (`LLM_TIMEOUT_S`). Si se excede o el LLM está caído, se entrega la plantilla de nivel 0 con un aviso corto.
- **Verificación de cifras** (ADR-002): si el texto trae un número que no está en el dato, se descarta y se usa la plantilla.
- **Fuente visible** al final: "Según tu inventario de hoy (actualizado 14:32)" o "Según *Condiciones Molino Sur.pdf*, pág. 2".

### Medición

Cada respuesta registra en `assistant_interaction`: nivel, intención, puntaje del enrutador, entidades, consultas, fuentes, acierto de caché, motivo de degradación, modelo, tokens generados, latencia total y del primer token. Con eso, T09 calcula el **% de consultas resueltas sin LLM** y la latencia por nivel, y T10 ajusta el umbral.

## Alternativas consideradas

- **Agente con tool calling por defecto:** descartado por los datos medidos (arriba).
- **LLM como clasificador de intenciones:** una llamada de ~2 s o más solo para clasificar, y con el 4B poco confiable. Los embeddings cuestan ~0.16 s.
- **Text-to-SQL:** riesgo de fuga entre pymes y de cifras incorrectas. Descartado (ADR-002).
- **Vectorizar el inventario y las recetas:** los datos estructurados se consultan, no se buscan por similitud; vectorizarlos da respuestas desactualizadas o aproximadas.

## Consecuencias

- La calidad del asistente depende de lo bien hecho que esté `intents.yaml`. Se mantiene como un artefacto de producto, no solo como código.
- Preguntas fuera del catálogo terminan en el nivel 2 o en "no sé". Se registran para decidir qué intenciones agregar.
- El nivel 3 queda como extensión opcional (`ASSISTANT_ENABLE_AGENT=false`).

## Implementación en T07 (10-nov-2026): lo que cambió respecto del diseño

- **Similitud con texto, no con embeddings.** El enrutador usa reglas y, si no alcanzan, `rapidfuzz` contra los ejemplos de `intents.yaml`. No necesita Ollama y responde en ~1 ms. Se cambia a `bge-m3` si la evaluación de T10 lo justifica.
- **Umbral provisional `0.65` y margen `0.03`** (`ASSISTANT_ROUTER_THRESHOLD`, `ASSISTANT_ROUTER_MARGIN`), elegidos con el barrido de `ml/evals/assistant/eval_router.py` para mantener el enrutamiento erróneo bajo 5 %. **No están calibrados** con un set reservado.
- **Nivel 1 apagado por defecto** (`ASSISTANT_USE_LLM=false`): la calidad de redacción en español de Chile no está medida (T10). Funciona sin *streaming* y se probó solo con un LLM simulado, no con Ollama.
- **Caché en memoria** por `(pyme_id, intención, pregunta normalizada, data_version de sus dominios, versión del catálogo, nivel, fecha)`; cubre niveles 0 y 1 y no guarda respuestas degradadas por LLM caído.
- **Segunda entrega (9-nov-2026):** nivel 2, SSE, feedback y las intenciones `order_detail`, `order_feasibility` y `production_summary` (abajo). **Sigue sin existir `cash_summary`**: depende de la pregunta abierta 3 del índice (si el registro de caja entra al MVP) y hoy no hay cómo registrar movimientos.
- **Resolución de entidades:** además de `rapidfuzz`, se desempata por cobertura del nombre ("empanadas de queso" gana a "Empanadas de pino"); con empate real se pregunta a la usuaria.

### Medido (equipo de referencia, base de desarrollo con datos de demo)
- **Enrutador, set dorado de 51 casos** (`ml/evals/assistant/golden.yaml`, escrito por una persona antes de ver resultados): primera corrida **45/51 (88,2 %)** con 4 mal enrutados. Tras corregir reglas y subir el umbral: **47/51 (92,2 %)** con 1 mal enrutado. **La segunda cifra es optimista**: se afinó contra el mismo set. T10 debe armar un set reservado.
- **Latencia del nivel 0** (`POST /assistant/ask`): p50 26 ms y p95 95 ms sin caché (n = 8, indicativo) y ~16 ms con caché; meta p95 ≤ 1,5 s.

### Segunda entrega de T07 (9-nov-2026)

- **Nivel 2.** Si la pregunta no calza con ninguna intención y la pyme tiene documentos, se hace una búsqueda híbrida: texto completo `spanish` **sin tildes** (`unaccent`; quien escribe "minimo" desde el celular encuentra "mínimo") y pgvector con `bge-m3`, fusionados por RRF. Se toman hasta `ASSISTANT_RAG_K` = 4 fragmentos (provisional); los que solo llegan por vector exigen similitud ≥ `ASSISTANT_RAG_MIN_SIMILARITY` = 0,45 (provisional, sin calibrar). Con el LLM apagado se muestra el mejor fragmento tal cual, citado (nivel 2 **extractivo**, sin LLM). Con el LLM encendido, este resume y cita. No se cachea. El reranker sigue sin implementarse (apagado por diseño hasta T10).
- **Streaming con verificación en el camino.** El LLM redacta en *streaming* y el texto se entrega por palabras completas. Antes de mostrar cada trozo se verifican todas sus cifras: si aparece una que no está en el dato, se corta la generación y se envía `replace` con la plantilla, así que **la usuaria nunca ve la cifra inventada**. También se corta por `LLM_TIMEOUT_S`. Se registra `first_token_ms`.
- **SSE** en el mismo `POST /assistant/ask` con `Accept: text/event-stream` (eventos `meta`, `delta`, `replace`, `done`; ver `docs/API.md`).
- **Precedencia de reglas (`overrides` en `intents.yaml`).** Las intenciones nuevas comparten palabras con las viejas ("pedido", "comprar"). En vez de dejar el empate a la similitud, cada intención declara a cuáles les gana cuando sus reglas coinciden (p. ej. `order_feasibility` gana a `low_stock` en "¿qué tengo que comprar para el pedido del sábado?"). Es determinista y se revisa en el YAML.
- **Métrica "sin LLM"** (T09): ahora cuenta las consultas en que **no se llamó** al LLM (`llm_model` nulo), lo que incluye el nivel 2 extractivo. Antes contaba solo el nivel 0.

#### Medido (equipo de referencia, base de desarrollo con datos de demo)
- **Enrutador, set dorado v2 (65 casos):** los 15 casos nuevos se escribieron **antes** de implementar las intenciones y sin mirar sus ejemplos; en la primera corrida se enrutaron bien los 15. Total **62/65 (95,4 %)**, con **0 enrutados a la intención equivocada** (los 3 que fallan quedan sin enrutar y piden aclaración). Salvedad: los casos y los ejemplos los escribió la misma persona; T10 sigue necesitando un set reservado con frases reales.
- **El benchmark de punta a punta encontró dos reglas demasiado amplias**, que se corrigieron: "¿Con cuánta anticipación **hay que** anular un evento?" caía en pedidos próximos y después en stock. Ese caso se agregó al set dorado **después** de corregirlo (no cuenta como ciego).
- **Latencia por SSE** (`ml/evals/assistant/bench_levels.py`; API con `ASSISTANT_USE_LLM=true` y sin caché; `qwen3:4b` y `bge-m3` en Ollama 0.40.15; n pequeño, indicativo):

| Nivel | n | Primer texto p50 / p95 | Completa p50 / p95 | Meta (propuesta) |
|-------|---|------------------------|--------------------|------------------|
| 0 | 15 | 11 / 13 ms | 13 / 19 ms | p95 ≤ 1,5 s ✔ |
| 1 | 5 | 1,3 / 1,9 s | 5,1 / 6,5 s | primer texto ≤ 3 s ✔; completa p95 ≤ 15 s ✔ |
| 2 | 10 | 1,7 / **6,6 s** | 4,7 / 8,6 s | primer texto ≤ 3 s **✘ en p95** (una corrida lenta); completa ✔ |

  El p95 del primer texto del nivel 2 **no cumple** la meta propuesta de 3 s, con n = 10. Las causas probables (sin confirmar) son la búsqueda con embeddings más un prompt más largo, que no reutiliza el prefijo en caché. Hay que repetir la medición con más casos en T10 antes de cambiar nada.
- **Calidad de redacción:** con la mitigación JSON, las respuestas medidas salieron en español, cortas y con las cifras del dato. **No hay evaluación humana todavía** (T10), así que `ASSISTANT_USE_LLM` sigue en `false` por defecto.
