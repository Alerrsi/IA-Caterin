# T07 — Asistente por niveles con RAG
- Estado: hecha (9-nov-2026), salvo `cash_summary` (bloqueada por la pregunta abierta 3); reranker y proveedor externo pasan a T10
- Depende de: T04
- Funcionalidad: F1

## Objetivo
Que la emprendedora pregunte "¿me alcanza la harina para el sábado?" o "¿cuánto me sale la docena de empanadas?" y reciba en segundos una respuesta correcta, con la fuente del dato, sin buscar en planillas.

## Contexto y decisiones previas
- Diseño completo: ADR-005. Reglas de cifras: ADR-002. Modelos: ADR-003.
- Determinista primero: nivel 0 sin LLM; niveles 1 y 2 con una sola llamada en *streaming*; nivel 3 apagado.
- Embeddings con `bge-m3` servidos por Ollama (a medir frente a lo medido con `sentence-transformers`).
- Supuesto: el umbral del enrutador arranca con un valor provisional configurable, que **no está medido**, hasta que T10 lo calibre.

## Entregables
- [x] `intents.yaml` con el catálogo inicial de ADR-005 (≥ 8 ejemplos por intención, en español de Chile) y su validación al cargar. — **hecho con 9 de las 10 intenciones del ADR; falta `cash_summary` (pregunta abierta 3: no hay registro de caja). Validación al cargar, más `overrides` para la precedencia de reglas**
- [x] Enrutador: reglas y palabras clave → similitud con `bge-m3` (embeddings de los ejemplos precalculados al iniciar) → umbral y margen. — **hecho con reglas + similitud de **texto** (`rapidfuzz`), no `bge-m3`: desviación documentada en ADR-005**
- [x] Resolución de entidades con `rapidfuzz` y fechas relativas en español de Chile (`America/Santiago`). — **hecho (`rapidfuzz` con desempate por cobertura; fechas y rangos en `America/Santiago`)**
- [x] Consultas tipadas de solo lectura (reusan los servicios de T04/T05) y plantillas de nivel 0. — **hecho: 6 consultas que reusan los servicios de T04**
- [x] `core/llm`: `LLMProvider` con Ollama (*streaming*, timeout, `keep_alive`) y la interfaz para un proveedor externo opcional. — **hecho: `chat_stream` (con salida JSON para que `qwen3:4b` no mezcle su razonamiento, ADR-003) y corte por `LLM_TIMEOUT_S`. La interfaz (`LLMProvider`) admite otro proveedor, pero no se implementó ninguno externo (opcional, T10)**
- [x] Nivel 1: redacción con dato compacto, verificación de cifras y degradación a plantilla. — **hecho con *streaming* y verificación de cifras antes de mostrar cada trozo; probado con LLM simulado y medido con Ollama real (ADR-005)**
- [x] Nivel 2: subida de documentos (PDF, XLSX, CSV, TXT), *chunking*, embeddings, búsqueda híbrida (pgvector + FTS `spanish`, fusión por RRF), 3 a 5 fragmentos, citas. Reranker detrás de un flag, apagado. — **hecho (FTS sin tildes con `unaccent`; hasta 4 fragmentos; sin LLM, el fragmento citado tal cual). El reranker NO se implementó: queda para T10, que decide si hace falta**
- [x] Caché por pyme con `data_version` (ADR-005). — **hecho (memoria del proceso, con `data_version`)**
- [x] `POST /assistant/ask` en SSE y JSON, `GET /assistant/quick-actions`, `POST /assistant/feedback`, `/documents`. — **hecho**
- [x] Registro completo en `assistant_interaction`. — **hecho, con `first_token_ms` y `feedback`**
- [x] Defensas contra prompt injection (SECURITY, sección 3). — **hecho: datos y fragmentos delimitados, `<`/`>` del documento neutralizados, instrucción de tratarlos como información, verificador de cifras en el camino y nada de acciones de escritura; prueba con un documento que intenta cerrar la etiqueta**
- [x] Set dorado inicial en `ml/evals/assistant/` (≥ 40 casos: preguntas de gestión formuladas de varias maneras, sin dato, ambiguas, inyección) y un script que mide el acierto del enrutador por nivel. — **hecho: 51 casos + `eval_router.py` (solo mide el enrutador)**
- [x] Medición de la latencia de `bge-m3` vía Ollama (p50/p95) registrada en ADR-003. — **hecho: p50 62 ms, p95 70 ms**

## Criterios de aceptación
- En el set dorado, las preguntas de las intenciones del catálogo se enrutan bien en ≥ 90% de los casos (**propuesta**; se informa el valor medido aunque no alcance).
- Nivel 0: p95 ≤ 1.5 s; niveles 1 y 2: primer texto ≤ 3 s y respuesta completa p95 ≤ 15 s, medido en el equipo de referencia (**propuesta** de AGENTS.md, a ratificar).
- Con Ollama apagado, las preguntas de nivel 1 devuelven la plantilla de nivel 0 en lugar de un error.
- Una respuesta con una cifra que no está en el dato se descarta (test con un LLM simulado que inventa un número).
- Ninguna respuesta incluye datos de otra pyme (test A/B, incluida la búsqueda de documentos).
- Toda respuesta muestra su fuente.

## Pruebas requeridas
- Unitarias: reglas del enrutador, resolución de fechas, *fuzzy matching*, verificador de cifras (formatos chilenos: "$21.000", "2,5 kg"), plantillas, clave de caché e invalidación.
- Integración: los tres niveles con un `LLMProvider` falso y con Ollama real (marcados como lentos), SSE, aislamiento A/B.
- Evaluación: set dorado (enrutador, exactitud, latencia); la evaluación de redacción y de RAG la amplía T10.

## Fuera de alcance
- Nivel 3 (agente), voz, acciones de escritura desde el chat.

## Riesgos y preguntas abiertas
- La calidad del enrutador depende de los ejemplos; conviene recoger frases reales de emprendedoras.
- La latencia de los niveles 1 y 2 en el VPS final puede ser peor que en el notebook; T11 lo vuelve a medir.
- Si los embeddings por Ollama rinden peor, cambiar a ONNX Runtime (ADR-003).

## Resumen de cierre (parcial, 10-nov-2026)
**Hecho.** Nivel 0 completo de punta a punta: catálogo `intents.yaml` (6 intenciones), enrutador sin LLM, resolución de entidades y fechas, consultas tipadas con plantillas, caché por pyme invalidada por `data_version`, registro en `assistant_interaction`, `POST /assistant/ask` (JSON) y `GET /assistant/quick-actions`. Nivel 1 con verificador de cifras y degradación a la plantilla (apagado por defecto). 34 pruebas del asistente, incluido el aislamiento entre pymes y la invalidación de caché.

**Medido.** Enrutador en el set dorado de 51 casos: 88,2 % en la primera corrida y 92,2 % tras afinar reglas y umbral (**optimista**, afinado contra el mismo set). Nivel 0: p95 95 ms sin caché (n = 8) frente a la meta de 1,5 s.

**Pendiente.** Nivel 2 y todo lo que implica (subida de documentos, *chunking*, embeddings, pgvector, búsqueda híbrida, reranker), *streaming* SSE, feedback, las 4 intenciones que faltan, medir `bge-m3` por Ollama y probar el nivel 1 con Ollama real.

**Riesgos.** El umbral (0,65) y el margen (0,03) son provisionales. Hasta que exista `order_feasibility`, preguntas como "¿me alcanza la harina para el pedido del sábado?" se enrutan por error a pedidos próximos. Las frases del catálogo y del set dorado las escribió una sola persona: conviene recoger frases reales de emprendedoras. Una pregunta con varias entidades ("harina y azúcar") solo resuelve una.

## Resumen de cierre (9-nov-2026)
**Hecho.** Nivel 2 (`/documents` con PDF/XLSX/CSV/TXT, fragmentos citables por página, hoja o filas, búsqueda híbrida sin tildes y con pgvector, aislada por pyme); SSE con verificación de cifras antes de mostrar cada trozo; `POST /assistant/feedback`; intenciones `order_detail`, `order_feasibility` (reusa el calculador de F3) y `production_summary` (invalida la caché al confirmar producción); precedencia de reglas con `overrides`; `bench_levels.py` para medir por nivel. 61 pruebas del asistente y de documentos (51 y 10; con LLM simulado y aislamiento A/B).

**Medido** (detalle en ADR-005). Enrutador: 62/65 en el set dorado v2, con 0 enrutados a la intención equivocada; los 15 casos nuevos acertaron en la primera corrida. Nivel 0: p95 19 ms. Nivel 1: primer texto p95 1,9 s y completa p95 6,5 s (n = 5). Nivel 2: primer texto p95 **6,6 s** (no cumple la meta propuesta de 3 s, con n = 10) y completa p95 8,6 s. `bge-m3` en Ollama: p95 70 ms.

**Hallazgo.** `qwen3:4b` en Ollama 0.40.15 escribe su razonamiento en inglés dentro del texto aunque se pida `think: false`. Se mitigó con salida JSON en el *streaming* (ADR-003). Esto suma un motivo para evaluar `qwen3:4b-instruct` en T10.

**Pendiente.** `cash_summary` (pregunta 3 del índice); reranker y proveedor externo (T10); calibrar el umbral del enrutador, `ASSISTANT_RAG_K` y la similitud mínima con un set reservado y documentos reales (T10); evaluación humana de la redacción antes de encender `ASSISTANT_USE_LLM` por defecto (T10); la pantalla de chat (T08).

**Riesgos.** En el nivel 2, cualquier coincidencia de texto (búsqueda OR de palabras) cuenta como relevante: con muchos documentos, una pregunta vaga podría responder con un fragmento poco pertinente. Hay que medirlo con documentos reales (T10). Además, `order_feasibility` mira un solo pedido y no descuenta el stock que piden los otros; la respuesta lo dice.
