# AGENTS.md — Cáterin

Instrucciones para agentes de IA (Claude Code u otros) que desarrollan este repositorio. Léelo completo antes de escribir código. Si algo aquí contradice una petición del usuario, gana el usuario; si contradice una tarea en `docs/tasks/`, pregunta.

## 1. Contexto del producto

Cáterin es un software de gestión con IA para **pymes de catering de La Araucanía, Chile**. Nace del informe "Detección de Oportunidades PYME – Cáterin" (Innovación y Emprendimiento III, INACAP Temuco).

**Pregunta de desafío:** ¿Cómo implementar IA para automatizar procesos de negocio de pymes de catering, reduciendo tiempos en finanzas, inventarios y comunicación con clientes en La Araucanía?

**Usuaria objetivo:** emprendedora de catering con poca experiencia técnica, poco tiempo, márgenes ajustados y, a veces, conectividad limitada. Desconfía de soluciones caras que "pierden capital".

**Principios de diseño (no negociables):**

1. **Ágil:** pocos clics, lenguaje simple en español de Chile.
2. **Centralizado:** una sola fuente de verdad para inventario, recetas, pedidos y finanzas.
3. **Accesible:** bajo costo, open source, fácil de alojar y mantener, mobile-first.
4. **Preciso:** los números los calcula código determinista y trazable, nunca el LLM.
5. **Eficiente (principio rector del asistente):** lo determinista va primero y el LLM es el último recurso. Cada consulta se resuelve con el camino más barato que la responda bien: reglas y consultas SQL, luego embeddings, y solo al final un modelo de lenguaje pequeño que redacta con datos ya resueltos. Se mide cuánto cuesta cada nivel y se optimiza por ahí, no subiendo el tamaño del modelo.

## 2. Alcance del MVP: 3 funcionalidades

| ID | Funcionalidad | Módulo API | Criterio de éxito |
|----|---------------|------------|-------------------|
| F1 | Asistente de gestión con RAG sobre el estado de la pyme | `modules/assistant` | Responde con datos reales y cita su fuente; latencia medida |
| F2 | Computer Vision desde el celular para identificar y contar productos finales | `modules/vision` | Foto → conteo por producto en pocos segundos, corregible por la usuaria |
| F3 | Cotización automatizada de materias primas según pedido | `modules/quotes` | Pedido → lista de insumos → cotización comparada → PDF, mucho más rápido que Excel |

Soporte transversal: auth multi-tenant, inventario, recetas, proveedores/precios, métricas.

**Fuera de alcance (no implementar sin pedido explícito):** robot de delivery, detección de ataques informáticos con ML, marketing con IA, app de voz, pagos, facturación electrónica SII, expansión de infraestructura de telecomunicaciones. Pueden quedar como ideas futuras en `docs/ROADMAP.md`.

## 3. Stack y decisiones

| Capa | Elección | Notas |
|------|----------|-------|
| Backend | Python 3.12, FastAPI, Pydantic v2 | Async donde aporte; sin sobreingeniería |
| BD | PostgreSQL 16 + pgvector | Una sola BD para datos relacionales y vectores |
| ORM/migraciones | SQLAlchemy 2.x, Alembic | Toda tabla cambia vía migración |
| LLM/RAG | LangChain para RAG y para la abstracción del LLM; sin bucle de agente por defecto | LLM detrás de una interfaz `LLMProvider` |
| LLM por defecto | Ollama + `qwen3:4b` para redactar y extraer; `qwen3:8b` solo como escalamiento opcional (ver 3.1) | Proveedor externo opcional por `.env` |
| Embeddings + reranker | `BAAI/bge-m3` + `BAAI/bge-reranker-v2-m3` (ver 3.1) | Vectores de 1024 dimensiones en pgvector |
| Visión | RF-DETR (Nano → Small), fine-tuning en PyTorch → export ONNX (ver 3.1) | Inferencia con ONNX Runtime en CPU |
| Frontend | React + Vite + TypeScript, PWA, Tailwind | Mobile-first, accesible (WCAG AA) |
| Infra | Docker Compose en un VPS pequeño, Caddy para HTTPS | Costo mensual bajo es un requisito |
| Calidad | pytest, ruff, mypy, pre-commit; Vitest + Playwright en web | CI en GitHub Actions |

Keras está permitido solo si hay una razón documentada en un ADR; el camino por defecto para visión es PyTorch. Si una elección de esta tabla resulta inviable, no la cambies en silencio: escribe un ADR y avisa.

### 3.1 Modelos de IA (decisión inicial, a ratificar en ADR-003)

Selección hecha en noviembre de 2026 con fuentes secundarias (blogs técnicos, model cards, documentación oficial). Los puntajes públicos orientan, pero **no reemplazan medir en el caso de Cáterin**. Si un dato de esta sección no se puede verificar en la model card o en la documentación oficial, el agente lo corrige y lo anota en el ADR.

**Criterios, en orden:** (1) licencia permisiva (Apache 2.0 o MIT); (2) corre en hardware barato (CPU de VPS o GPU de 12 GB); (3) buen español; (4) buena redacción y extracción en español, o exportación ONNX en el caso de visión; (5) calidad. El tool calling ya no es criterio de elección del modelo por defecto: el enrutamiento del asistente es determinista (ver F1).

**Regla de cambio:** se usa el modelo por defecto salvo que la evaluación propia (T10) muestre que un candidato es mejor. Cambiar de modelo exige actualizar ADR-003 y `models.lock.yaml`.

#### LLM (asistente F1 y extractor de pedidos F3)

| Rol | Modelo | Tag Ollama | Licencia | Motivo |
|-----|--------|------------|----------|--------|
| **Por defecto (redactar y extraer)** | Qwen3 4B | `qwen3:4b` | Apache 2.0 | Medido en CPU: 7.5 tokens/s, prefill de 1.2 s, extracción 7/8. Con el diseño por niveles el modelo solo redacta datos ya resueltos y extrae pedidos, así que no necesita tool calling |
| Candidato a evaluar | Qwen3 4B Instruct | `qwen3:4b-instruct` (tag citado por una fuente; verificar en Ollama) | Apache 2.0 | Variante sin thinking, más liviana; una fuente la recomienda para equipos con poca memoria |
| Candidato a evaluar | Gemma 4 E4B | verificar en ollama.com/library | Apache 2.0 | Tamaño comparable, function calling nativo, 140+ idiomas; a medir en redacción en español de Chile |
| Escalamiento opcional (Nivel 3, agente) | Qwen3 8B | `qwen3:8b` | Apache 2.0 | Único que pasó tool calling (4/4), pero a 4.3 tokens/s y con p95 de 25 s. Apagado por defecto; para GPU o proveedor externo. `qwen3:14b` queda en la misma categoría (no probado) |

**Descartados:** Llama 4 (licencia comunitaria, no OSI), Gemma 3 (términos de uso de Google), Phi-4 14B (tool calling débil según las fuentes), Qwen3.8-Max y variantes con licencia propia, modelos de más de 30B (no caben en el hardware objetivo). `llama3.1:8b` queda solo como baseline de comparación.

**Configuración base:**
- Temperatura 0 a 0.2 para extracción y herramientas.
- Thinking desactivado por defecto (latencia); activarlo solo donde la evaluación demuestre beneficio.
- Salida estructurada con JSON schema validado por Pydantic en el extractor de pedidos.
- Contexto de 2k a 4k tokens: solo se le pasa el dato ya resuelto en formato compacto, nunca el inventario completo. Mantener fijo el prefijo del prompt (sistema y formato) para que Ollama reutilice el caché entre consultas.
- Respuestas cortas por diseño: tope de unos 120 tokens (`num_predict`) e instrucción de responder en pocas frases.
- Todo acceso pasa por `LLMProvider`.

**Resultados medidos en CPU (9-nov-2026).** Equipo: ThinkPad con i5-8250U (4 núcleos, 8 hilos), 16 GB de RAM, Debian 13, sin GPU. Fuente: `ml/bench/bench_results.json` generado con `ml/bench/bench_cpu.py`. El equipo se ralentizó de forma intermitente durante las pruebas, así que los tiempos pueden estar algo inflados.

| Modelo | Tokens/s (p50) | Prefill (~300 tokens) | Latencia total p50 / p95 | Tool calling | Extracción de pedidos |
|--------|----------------|-----------------------|--------------------------|--------------|-----------------------|
| `qwen3:4b` | 7.5 | 1.2 s | 22.7 s / 26.1 s | **1/4** | 7/8 |
| `qwen3:8b` | 4.3 | 2.7 s | 11.1 s / 25.2 s | **4/4** | 7/8 |

Carga inicial: 7.4 s (4B) y 31.8 s (8B). Cada modelo corrió 12 preguntas, 4 casos de tool calling y 3 de extracción: son pocos casos y sirven para descartar, no para fijar porcentajes.

**Lectura de los resultados:**
- **Tool calling:** solo `qwen3:8b` eligió bien la herramienta (4/4). `qwen3:4b` falló los tres casos que exigían llamar una herramienta y solo acertó el caso sin herramienta, que pasa cualquier modelo que nunca llame. Por eso el asistente **no depende de que el LLM elija herramientas**: el enrutamiento es determinista (ver F1) y el modelo chico solo redacta. El agente con herramientas (Nivel 3) queda opcional, con `qwen3:8b`, pensado para GPU o proveedor externo.
- **Extracción:** ambos sacaron 7/8 campos. El script todavía no registra qué campo falló (se corrige en T10). `qwen3:4b` es el modelo por defecto para extraer pedidos (F3), siempre con confirmación de la usuaria; se valida con más casos en T10.
- **Redacción:** el benchmark actual no mide la calidad de redacción en español de Chile. Es una evaluación pendiente de T10 y condiciona la elección final entre `qwen3:4b`, `qwen3:4b-instruct` y Gemma 4 E4B.
- **No comparar modelos por p50 de latencia.** La latencia total depende sobre todo de cuántos tokens genera cada respuesta (tope de 160). Por eso el 4B marca 22.7 s frente a 11.1 s del 8B pese a ser más rápido por token: probablemente respondió más largo. No se puede confirmar porque la primera versión del script no registraba los tokens generados. Comparar por tokens/s y prefill hasta repetir.
- **RAM:** el `ram_gb` de ese JSON (3.2 GB en ambos modelos) no es confiable. Tiene un bug de coincidencia por prefijo que **sigue presente** en `ml/bench/bench_cpu.py` (ver ADR-003); se corrige en T10. Pendiente repetir.
- **El agente con 8B no cumple una latencia razonable en este equipo.** El p95 fue de 25.2 s en una sola llamada y un agente con herramientas necesita al menos dos (estimación). Por eso no es el camino por defecto.
- **Presupuestos de latencia del asistente (propuesta a ratificar por el equipo y validar con `bench_cpu.py` en un equipo tipo i5-8250U):**
  - Nivel 0 (sin LLM): p95 ≤ 1.5 s.
  - Niveles 1 y 2 (un llamado corto al LLM, con *streaming*): primer texto visible ≤ 3 s y respuesta completa p95 ≤ 15 s. Estimación: unos 80 tokens a 7.5 tokens/s son ~11 s, más ~1 s de prefill.
  - Si el VPS final es más lento, se ajustan los presupuestos o se recurre a GPU puntual o proveedor externo con datos minimizados y consentimiento.
- **`qwen3:14b` no se probó.** Por tamaño (~9 GB) se esperaría cerca de la mitad de tokens/s que el 8B (estimación); queda para GPU o proveedor externo.

#### Embeddings y reranker (RAG de F1)

| Rol | Modelo | Licencia | Motivo |
|-----|--------|----------|--------|
| **Embeddings por defecto** | `BAAI/bge-m3` | MIT | 568M parámetros, 1024 dimensiones, contexto de 8K; produce vectores densos, dispersos y multi-vector; fuerte en español; corre en CPU |
| Candidato a evaluar | `Qwen/Qwen3-Embedding-0.6B` | Apache 2.0 | Una fuente lo reporta por sobre BGE-M3 en MTEB multilingüe (64.33 vs 59.56; otras fuentes dan para BGE-M3 entre 59.56 y ~67, así que la comparación no es concluyente); contexto de 32K |
| **Reranker** | `BAAI/bge-reranker-v2-m3` | Permisiva (confirmar texto exacto en la model card) | Cross-encoder multilingüe pensado para acompañar a BGE-M3 |

**Pipeline:** búsqueda híbrida (pgvector + full-text search de Postgres con configuración `spanish`) para traer 10 a 20 candidatos → (opcional) reranker sobre los 10 mejores → 3 a 5 fragmentos al LLM. El reranker está **apagado por defecto** y se activa solo si mejora recall@5 en la evaluación de T10, porque cuesta CPU.

**Resultados medidos en CPU (mismo equipo que el LLM):**

| Modelo | Consulta p50 / p95 | 12 pasajes | recall@1 (test de humo) |
|--------|--------------------|------------|-------------------------|
| `bge-m3` | 156 ms / 235 ms | 2.8 s | 1.0 |
| `Qwen3-Embedding-0.6B` | 807 ms / 912 ms | 12.1 s | 1.0 |
| `bge-reranker-v2-m3` | 0.8 s con 5 candidatos; 3.7 s con 20 | — | sin cambio (ya era 1.0) |

- **`bge-m3` queda por defecto:** igual de preciso en el test de humo y unas 5 veces más rápido en consulta.
- **El test de humo está saturado.** Con 12 pasajes sintéticos ambos modelos aciertan todo, así que no discrimina. La decisión final espera la evaluación de T10 con documentos reales; `Qwen3-Embedding-0.6B` solo reemplaza a `bge-m3` si ahí muestra una mejora clara que compense su lentitud.
- **Reranker:** no mostró beneficio medible porque no había margen de mejora, y cuesta cerca de 0.8 s con 5 candidatos y 3.7 s con 20. Si se activa, solo sobre 10 candidatos o menos.
- Los tiempos de carga (60 a 80 s) probablemente incluyen la descarga inicial de los pesos; no usarlos como referencia.

**Descartados:** Qwen3-Embedding-8B, harrier-oss-v1-27b y otros modelos grandes (requieren GPU), NV-Embed-v2 (CC-BY-NC), rerankers Jina v2 (CC-BY-NC) y APIs de embeddings de pago.

**Regla de esquema:** la dimensión del vector queda fija en la migración. Cada fragmento guarda `embedding_model` y `embedding_version`; cambiar de modelo implica reindexar con una migración explícita.

#### Visión por computador (F2)

| Rol | Modelo | Licencia | Motivo |
|-----|--------|----------|--------|
| **Detector por defecto** | RF-DETR Nano; subir a Small si la precisión no alcanza | Apache 2.0 (Nano a Large) | Detector NMS-free con backbone DINOv2; se afina con datasets en formato COCO o YOLO; `model.export()` genera ONNX para ONNX Runtime; en COCO, Nano reporta AP50:95 de 48.4 y 2.3 ms en GPU T4 |
| Fallback | RT-DETRv2 o D-FINE | Apache 2.0 | Si RF-DETR resulta demasiado lento en CPU |
| Pre-etiquetado (no va a producción) | Grounding DINO o Florence-2 | Apache 2.0 / MIT | Sugieren cajas para que la persona las corrija y se ahorre etiquetado manual |
| Clasificación de recortes (solo si hace falta distinguir productos muy parecidos) | Backbone ligero de timm o torchvision (MobileNetV3, EfficientNet) | Verificar licencia de los pesos usados | Segunda etapa opcional sobre las cajas detectadas |

**Resultado medido en CPU (mismo equipo):** RF-DETR Nano exportado a ONNX, entrada de 384×384, 8 hilos: p50 de 169 ms, p95 de 199 ms (unos 5.9 cuadros por segundo) y carga de 0.6 s. Para una foto puntual sobra; para video no alcanza. Límites: se midió con una imagen aleatoria (sin decodificación ni postprocesamiento) y no se midió precisión. Falta repetir en el VPS objetivo y con el modelo ajustado a productos reales, y registrarlo en el model card. Las cifras de GPU T4 de la tabla anterior no aplican a CPU.

**Descartados:**
- Ultralytics YOLO12 y YOLO26: AGPL-3.0 con licencia comercial aparte. Son técnicamente muy buenos en CPU, así que usarlos exige un ADR que evalúe las consecuencias de la licencia para el proyecto y su publicación.
- DINOv3: tiene licencia propia (uso comercial permitido, pero exige incluir la licencia, mostrar "Built with DINOv3" y cumplir otras condiciones). No se usa por defecto.
- RF-DETR XL y 2XL: licencia PML 1.0.
- Keras: sin razón documentada para usarlo aquí.

**Entrenamiento:** reproducible (semilla, versión del dataset con manifiesto y hash), en una GPU gratuita tipo Colab o Kaggle, o local. Sin datos reales se parte de pocas decenas de imágenes por producto como punto de arranque y se valida con una curva de aprendizaje, no con una cifra supuesta. Métricas a reportar por producto: mAP50, mAP50:95, error absoluto medio de conteo y porcentaje de fotos con conteo exacto. El umbral objetivo se fija en el model card una vez medida la línea base.

#### Control de versiones de modelos

- `models.lock.yaml` en la raíz: identificador (Hugging Face u Ollama), revisión fija, licencia, tamaño y sha256 de cada ONNX; un script verifica que coincidan.
- Los pesos no se commitean; se descargan por script o se publican en releases.
- `THIRD_PARTY_NOTICES.md` con atribuciones y licencias de cada modelo y dependencia.
- Cada modelo tiene su model card en `ml/` o `docs/models/`.

#### Evaluación para decidir (la ejecuta T10)

| Componente | Set de evaluación | Métricas |
|------------|-------------------|----------|
| Asistente y LLM | 40 a 60 casos en español de Chile: preguntas de gestión (formuladas de varias maneras), pedidos de catering, preguntas sin dato, preguntas ambiguas | Acierto del enrutador de intenciones por nivel, exactitud de los datos, cifras de la redacción presentes en el dato de entrada, calidad de la redacción (revisión humana), exactitud del extractor campo a campo, tasa de alucinación, latencia p50/p95 por nivel, tokens generados, RAM |
| Embeddings y reranker | 50 o más preguntas sobre documentos reales o sintéticos | recall@5, MRR, latencia |
| Visión | Split de test sin fuga, con fotos reales de celular | mAP, error de conteo, latencia en CPU |

**Pruebas pendientes tras la primera ronda:** repetir `bench_cpu.py llm` (versión corregida, que registra tokens generados, RAM por modelo y detalle de fallos) con `qwen3:4b`, `qwen3:4b-instruct` y Gemma 4 E4B (verificando el tag). El benchmark no mide calidad de redacción: T10 debe agregarla con revisión humana. `qwen3:8b` y `qwen3:14b` solo se evalúan para el Nivel 3 opcional, en GPU o con proveedor externo. Para embeddings, repetir `bge-m3` contra `Qwen3-Embedding-0.6B` con documentos reales, con y sin reranker, y calibrar el umbral del enrutador de intenciones.

## 4. Reglas de arquitectura

- **El LLM no hace aritmética ni decide precios.** Cantidades, costos, totales e impuestos se calculan en código (`Decimal`, nunca `float` para dinero, moneda CLP sin decimales). El LLM solo: (a) extrae/normaliza texto a estructuras validadas con Pydantic, (b) redacta respuestas a partir de datos que la herramienta le entrega.
- **Asistente por niveles: determinista primero, LLM al final** (detalle en F1). Nada de text-to-SQL libre ni de bucle de agente por defecto. Las consultas son funciones tipadas de solo lectura (`get_stock`, `get_recipe_cost`, `list_upcoming_orders`, `get_cash_summary`, …) que filtran siempre por `pyme_id`. Cualquier acción que modifique datos exige confirmación explícita de la usuaria.
- **Multi-tenant:** toda tabla de negocio lleva `pyme_id`; toda consulta lo filtra desde una dependencia central, no a mano. Hay tests que prueban que una pyme no ve datos de otra.
- **Proveedor de LLM intercambiable** y **modelo de visión versionado**; ningún módulo importa un SDK de LLM directamente fuera de `core/llm`.
- **Tolerancia a baja conectividad:** la PWA cachea catálogos y recetas, encola escrituras sin red y sincroniza al volver. Las respuestas de la API son pequeñas y paginadas. Documentar qué funciona offline y qué no.
- **Trazabilidad:** cada cotización guarda versión de precios, supuestos y quién la generó. Cada respuesta del asistente guarda herramientas invocadas y fuentes.
- **Datos personales:** mínimos necesarios (Ley 19.628 y su actualización vigente en Chile). No enviar datos de clientes a proveedores externos de LLM sin que esté configurado y documentado.

### F1 — Asistente de gestión (por niveles, determinista primero)

**Idea central:** la mayoría de las preguntas de una pyme son pocas y repetitivas (¿cuánto me queda de X?, ¿cuánto cuesta esta receta?, ¿qué pedidos tengo?, ¿cómo va la caja?). No hace falta un agente para responderlas: se reconoce la intención, se ejecuta la consulta en código y se responde. El LLM entra solo cuando aporta algo que el código no puede dar.

| Nivel | Cuándo | Cómo | LLM | Meta (propuesta, ver 3.1) |
|-------|--------|------|-----|---------------------------|
| **0** | Intención clara y datos resueltos (el caso más frecuente) | Enrutador → consulta tipada → **plantilla de respuesta** | Ninguno | p95 ≤ 1.5 s |
| **1** | La respuesta se beneficia de lenguaje natural (resumen, comparación, explicación breve) | Mismo enrutador y consulta; el LLM redacta con el dato compacto | 1 llamada corta, en *streaming* | Primer texto ≤ 3 s; completa p95 ≤ 15 s |
| **2** | Pregunta abierta sobre documentos (políticas, condiciones de proveedores, recetas subidas) | Búsqueda híbrida (+ reranker opcional) → 3 a 5 fragmentos → LLM redacta y cita | 1 llamada corta, en *streaming* | Igual que nivel 1 |
| **3** | Opcional, apagado por defecto: preguntas que cruzan varias consultas | Agente con herramientas de solo lectura (`qwen3:8b`, GPU o proveedor externo) | Varias llamadas | Fuera del camino por defecto |

**Cómo se enruta (sin LLM):**
1. **Catálogo de intenciones** en un archivo versionado (`intents.yaml`): nombre, ejemplos de frases en español de Chile, consulta asociada, plantilla y si admite nivel 1.
2. **Reconocimiento:** reglas y palabras clave para lo obvio; para el resto, similitud de embeddings con `bge-m3` contra los ejemplos de cada intención (medido: ~0.16 s por consulta en CPU). Si la similitud supera el umbral calibrado en T10, se enruta; si no, nivel 2 o pregunta de aclaración.
3. **Resolución de entidades en código:** nombres de insumos, recetas y proveedores se resuelven por coincidencia aproximada contra la base (p. ej. `rapidfuzz`, licencia MIT), y las fechas ("mañana", "esta semana") con reglas. Si hay ambigüedad, se le ofrecen opciones a la usuaria; el modelo no adivina.
4. **Rutas rápidas en la interfaz:** botones con las preguntas frecuentes, que entran directo al nivel 0 sin escribir ni reconocer nada.

**Reglas de eficiencia:**
- **Caché por pyme:** respuestas de nivel 0 y 1 se cachean con una clave que incluye la versión de los datos; cualquier escritura relevante la invalida.
- **Contexto mínimo:** al LLM solo se le pasa el resultado de la consulta en formato compacto, nunca el inventario completo ni el historial largo.
- **Respuesta corta y en *streaming*:** tope de ~120 tokens; la usuaria ve texto en pocos segundos aunque la respuesta completa tarde más.
- **Un solo llamado al LLM por consulta** en los niveles 1 y 2. Si el camino exige más, no es camino por defecto.
- **Degradación elegante:** si el LLM no está disponible o tarda más que un máximo configurable, se entrega la plantilla de nivel 0 con el dato crudo en lugar de un error.
- **Medición por nivel:** cada respuesta registra nivel usado, intención, latencia y tokens generados. Es la base de la métrica de tiempo de respuesta (T09) y del ajuste del umbral del enrutador.

**Reglas de calidad y seguridad (aplican a todos los niveles):**
- Datos estructurados (stock, costos, pedidos) se consultan por funciones, no se vectorizan. Solo los documentos subidos (PDF/Excel/CSV/texto) pasan por chunking → embeddings → pgvector, con metadatos (`pyme_id`, origen, fecha).
- Respuestas en español de Chile, cortas, con fuente visible ("según tu inventario de hoy…"). Si no hay dato, dice que no lo tiene; no inventa.
- El LLM redacta a partir del dato que recibe y no puede agregar cifras: se verifica que los números de la respuesta aparezcan en el dato de entrada; si no, se descarta y se usa la plantilla.
- Defensa contra prompt injection: el contenido de documentos y proveedores se trata como datos, nunca como instrucciones.
- Se evalúa con un set de preguntas doradas (`ml/evals/assistant`) que mide acierto del enrutador por nivel, exactitud de los datos, calidad de la redacción y latencia.

### F2 — Computer Vision
- Alcance inicial: **detección y conteo de productos finales** de la pyme (p. ej. canapés, empanaditas, brochetas) desde foto de celular, con RF-DETR (ver 3.1). Una clasificación de recortes como segunda etapa solo se agrega si las métricas muestran confusión entre productos parecidos.
- Flujo: foto → inferencia ONNX → resultado editable por la usuaria → se registra en producción/inventario. La corrección humana se guarda como dato para reentrenar.
- Dataset: estructura documentada, split train/val/test sin fuga, augmentations realistas (luz de cocina, ángulos de celular). Reportar métricas por clase y matriz de confusión en `ml/vision/MODEL_CARD.md`.
- Sin dataset real al inicio: usar un dataset público como base (p. ej. Food-101) para validar el pipeline y dejar claro en el model card que no representa el producto final. Nunca presentar métricas de dataset público como si fueran del caso real.
- El modelo debe correr en CPU de un VPS pequeño con latencia aceptable; medirla.

### F3 — Cotización automatizada
- Entrada: pedido (texto libre, lista o formulario) → extractor LLM a esquema validado → resolución contra recetas → **cantidad de insumos** (cálculo determinista, con merma configurable) → **descuento de stock** disponible → **lista de compras** → **comparación de precios** de proveedores → cotización PDF para el cliente final.
- Fuentes de precios: catálogo de proveedores cargado por la usuaria (CSV/Excel), ingreso manual e importación de listas. Scraping de sitios públicos solo si los términos del sitio lo permiten, detrás de una interfaz `PriceSource`, con caché y respeto a `robots.txt`. No scrapear sin que esté aprobado en un ADR.
- Cada línea muestra proveedor, precio, fecha del precio y unidad normalizada (kg, g, L, unidad).
- **Extracción eficiente y segura:** el extractor usa `qwen3:4b` con salida estructurada y tope de tokens bajo. El pedido interpretado se muestra en una tabla editable y la usuaria lo confirma antes de calcular. Si el JSON no valida, se reintenta una vez y, si vuelve a fallar, se ofrece el formulario manual. El modelo nunca calcula cantidades ni precios.
- Tests con casos reales de catering (conversión de unidades, mermas, redondeos, proveedor sin stock).

## 5. Convenciones de código

- Python tipado; `ruff` y `mypy --strict` en módulos nuevos. Funciones pequeñas, módulos con una responsabilidad.
- API: rutas versionadas `/api/v1`, errores en formato único (RFC 9457 problem details), OpenAPI siempre actualizado.
- Configuración solo por variables de entorno (`pydantic-settings`). **Jamás** commitear secretos; mantener `.env.example`.
- Logs estructurados, sin datos personales ni prompts completos en nivel INFO.
- Frontend: componentes accesibles, textos en un archivo de i18n (es-CL), lenguaje simple, máximo 3 clics para las acciones principales, botones grandes, contraste AA.
- Nombres de código en inglés; textos de UI, documentación y mensajes de error visibles a la usuaria en español de Chile.
- Dependencias: añadir solo con motivo; preferir licencias permisivas; fijar versiones.

## 6. Flujo de trabajo del agente

1. Lee este archivo, `README.md` y el documento de tarea (`docs/tasks/Txx-*.md`) antes de actuar.
2. **Primera sesión:** crea los documentos de la sección 7 antes de escribir código de producto.
3. Trabaja **una tarea a la vez**, en una rama `feat/Txx-descripcion-corta`.
4. Commits pequeños con Conventional Commits y el ID de tarea:
   `feat(quotes): calcular insumos por receta [T05]`
5. Cada tarea termina cuando cumple su **Definición de Hecho** (sección 8). Marca el estado en `docs/tasks/00-INDEX.md`.
6. Si falta información (credenciales, datos reales, decisiones de negocio), **pregunta o deja un supuesto explícito** en el documento de tarea; no inventes datos de negocio.
7. Actualiza la documentación afectada en el mismo cambio de código.
8. Al cerrar una tarea deja un resumen corto en su documento: qué se hizo, qué quedó pendiente, riesgos.

Antes de ejecutar acciones destructivas (borrar datos, `docker volume rm`, reescribir historia de git, migraciones irreversibles), pide confirmación.

## 7. Documentos que el agente debe crear

### 7.1 Documentos de proyecto (crear en la primera sesión)

| Archivo | Contenido mínimo |
|---------|------------------|
| `docs/ARCHITECTURE.md` | Diagrama de componentes, flujo de cada funcionalidad (F1–F3), límites de módulos, estrategia offline, estimación de costo mensual de hosting |
| `docs/DATA_MODEL.md` | Entidades y relaciones (Pyme, Usuario, Insumo, Proveedor, PrecioInsumo, Receta, LineaReceta, Pedido, Cotización, LineaCotización, ProducciónRegistrada, Documento, MétricaEvento), reglas de multi-tenancy, unidades y moneda |
| `docs/API.md` | Resumen de endpoints por módulo, auth, errores, paginación |
| `docs/adr/ADR-001-stack.md` | Justificación del stack de la sección 3 |
| `docs/adr/ADR-002-calculo-determinista.md` | Por qué el LLM no calcula |
| `docs/adr/ADR-003-modelos-ia.md` | Ratificación o cambio de los modelos de la sección 3.1: resultados del benchmark propio (latencia, RAM, calidad en español), verificación de licencias y modelo final elegido por componente |
| `docs/adr/ADR-004-offline-pwa.md` | Qué funciona sin conexión y cómo se sincroniza |
| `docs/adr/ADR-005-asistente-por-niveles.md` | Por qué el asistente es determinista primero y el LLM al final (resultados medidos de 3.1), catálogo de intenciones, umbral del enrutador, caché y presupuestos de latencia por nivel |
| `docs/SECURITY.md` | Multi-tenancy, prompt injection, manejo de datos personales, gestión de secretos |
| `docs/ROADMAP.md` | Ideas descartadas del brainstorming y trabajo futuro |

### 7.2 Documentos de tareas (`docs/tasks/`)

Crea `docs/tasks/00-INDEX.md` (tabla con ID, título, estado, dependencias, dueño de la tarea) y un archivo por tarea con la plantilla de 7.3. Tareas a crear:

| ID | Archivo | Objetivo | Depende de |
|----|---------|----------|------------|
| T01 | `T01-fundaciones.md` | Monorepo, Docker Compose, CI, lint/format/tipos, `.env.example`, healthchecks, comandos de arranque verificados | — |
| T02 | `T02-modelo-datos.md` | Modelos SQLAlchemy, migraciones Alembic, seed con datos realistas de catering en CLP | T01 |
| T03 | `T03-auth-multitenant.md` | Registro/login JWT, roles (dueña, colaboradora), aislamiento por `pyme_id` con tests | T02 |
| T04 | `T04-inventario-recetas-proveedores.md` | CRUD de insumos, stock, recetas con costo calculado, proveedores y precios, import CSV/Excel | T03 |
| T05 | `T05-cotizador-f3.md` | Extractor de pedidos, cálculo de insumos, comparación de precios, PDF de cotización, trazabilidad | T04 |
| T06 | `T06-vision-f2.md` | Pipeline de datos, pre-etiquetado, fine-tuning de RF-DETR en PyTorch, export ONNX, endpoint de inferencia, flujo de corrección, model card | T04 |
| T07 | `T07-asistente-rag-f1.md` | Catálogo de intenciones y enrutador (reglas + embeddings), resolución de entidades, consultas de solo lectura con plantillas (nivel 0), redacción con LLM en *streaming* (nivel 1), RAG para preguntas abiertas (nivel 2), caché, verificación de cifras, citas de fuente, defensas, set de evaluación. El nivel 3 (agente) queda como extensión opcional | T04 |
| T08 | `T08-frontend-pwa.md` | PWA mobile-first: inicio simple, inventario, cotizar, foto de producción, chat; offline básico; accesibilidad | T05, T06, T07 (por pantallas) |
| T09 | `T09-metricas.md` | Encuesta 1–5 estrellas, tiempo de cotización (antes/después), latencia del asistente por nivel y porcentaje de consultas resueltas sin LLM, endpoint y panel de métricas | T05, T07, T08 |
| T10 | `T10-calidad-evals.md` | Cobertura mínima, tests e2e, evaluación del RAG y del extractor, evaluación de visión, pruebas de carga ligera | T05–T07 |
| T11 | `T11-despliegue.md` | Compose de producción, HTTPS con Caddy, backups de Postgres, observabilidad básica, costo mensual documentado | T08 |
| T12 | `T12-documentacion-demo.md` | README final verificado, guía de usuario en lenguaje simple, guion de demo de 10 min, datos de demo | T09–T11 |

Orden recomendado: T01 → T02 → T03 → T04 → (T05, T06, T07 en paralelo si hay capacidad) → T08 → T09 → T10 → T11 → T12.

### 7.3 Plantilla de documento de tarea

```markdown
# Txx — Título
- Estado: pendiente | en curso | bloqueada | hecha
- Depende de: Txx
- Funcionalidad: F1 | F2 | F3 | transversal

## Objetivo
(1–3 frases, en términos de valor para la emprendedora)

## Contexto y decisiones previas
(enlaces a ADR, supuestos explícitos)

## Entregables
- [ ] ...

## Criterios de aceptación
(verificables: comandos, endpoints, pantallas, métricas con umbral)

## Pruebas requeridas
(unitarias, integración, e2e, evaluación)

## Fuera de alcance
- ...

## Riesgos y preguntas abiertas
- ...

## Resumen de cierre
(se completa al terminar)
```

## 8. Definición de Hecho (cualquier tarea)

- Código con tipos, lint y tests pasando en CI.
- Migraciones aplicables desde cero y reversibles cuando sea posible.
- Tests de aislamiento multi-tenant si se tocan datos de negocio.
- Documentación y OpenAPI actualizadas.
- Sin secretos, sin datos personales reales, sin `TODO` sin dueño ni tarea asociada.
- Comandos del README y de la tarea ejecutados y verificados, no solo escritos.
- Estado actualizado en `docs/tasks/00-INDEX.md`.

## 9. Criterios de aceptación globales del MVP

- Una usuaria nueva carga insumos y una receta, y obtiene su primera cotización con PDF sin ayuda técnica.
- El tiempo de cotización con Cáterin es medible y comparable con el proceso manual de referencia (se mide, no se asume).
- El asistente responde preguntas de inventario, costos y pedidos con datos correctos en el set de evaluación, y dice "no sé" cuando corresponde. Las preguntas frecuentes se resuelven sin LLM y en pocos segundos en un notebook de gama media (referencia medida: i5-8250U, sin GPU).
- La foto de producción devuelve un conteo editable; las correcciones quedan registradas.
- La app es usable en un celular de gama media, y las pantallas clave funcionan o degradan con gracia con red inestable.
- Costo mensual de operación documentado y bajo.

## 10. Honestidad con los datos

- No presentes como medidos resultados que no se midieron. Las cifras de Winnow o MarketMan del informe provienen de las propias empresas; úsalas solo como referencia.
- Marca claramente los datos sintéticos o de demo.
- Si una métrica no alcanza el umbral, repórtalo y propón alternativas en lugar de ajustar el criterio.
