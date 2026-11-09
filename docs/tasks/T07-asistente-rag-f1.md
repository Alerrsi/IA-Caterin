# T07 — Asistente por niveles con RAG
- Estado: en curso (nivel 0 y nivel 1 básico listos; faltan nivel 2, SSE y feedback)
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
- [x] `intents.yaml` con el catálogo inicial de ADR-005 (≥ 8 ejemplos por intención, en español de Chile) y su validación al cargar. — **hecho con 6 de las 10 intenciones del ADR (faltan `order_detail`, `order_feasibility`, `cash_summary`, `production_summary`); validación al cargar**
- [x] Enrutador: reglas y palabras clave → similitud con `bge-m3` (embeddings de los ejemplos precalculados al iniciar) → umbral y margen. — **hecho con reglas + similitud de **texto** (`rapidfuzz`), no `bge-m3`: desviación documentada en ADR-005**
- [x] Resolución de entidades con `rapidfuzz` y fechas relativas en español de Chile (`America/Santiago`). — **hecho (`rapidfuzz` con desempate por cobertura; fechas y rangos en `America/Santiago`)**
- [x] Consultas tipadas de solo lectura (reusan los servicios de T04/T05) y plantillas de nivel 0. — **hecho: 6 consultas que reusan los servicios de T04**
- [ ] `core/llm`: `LLMProvider` con Ollama (*streaming*, timeout, `keep_alive`) y la interfaz para un proveedor externo opcional. — **parcial: `chat_json` sin *streaming*; falta `chat` en texto con *streaming* y la interfaz de proveedor externo**
- [x] Nivel 1: redacción con dato compacto, verificación de cifras y degradación a plantilla. — **hecho sin *streaming*; probado con LLM simulado, **no con Ollama real****
- [ ] Nivel 2: subida de documentos (PDF, XLSX, CSV, TXT), *chunking*, embeddings, búsqueda híbrida (pgvector + FTS `spanish`, fusión por RRF), 3 a 5 fragmentos, citas. Reranker detrás de un flag, apagado. — **NO hecho: documentos, *chunking*, embeddings y búsqueda híbrida**
- [x] Caché por pyme con `data_version` (ADR-005). — **hecho (memoria del proceso, con `data_version`)**
- [ ] `POST /assistant/ask` en SSE y JSON, `GET /assistant/quick-actions`, `POST /assistant/feedback`, `/documents`. — **parcial: solo JSON y `quick-actions`; faltan SSE, `feedback` y `/documents`**
- [x] Registro completo en `assistant_interaction`. — **hecho (`first_token_ms` queda vacío hasta que haya *streaming*)**
- [ ] Defensas contra prompt injection (SECURITY, sección 3). — **parcial: datos delimitados, instrucción de tratarlos como información, verificador de cifras y nada de acciones de escritura; las defensas sobre documentos esperan al nivel 2**
- [x] Set dorado inicial en `ml/evals/assistant/` (≥ 40 casos: preguntas de gestión formuladas de varias maneras, sin dato, ambiguas, inyección) y un script que mide el acierto del enrutador por nivel. — **hecho: 51 casos + `eval_router.py` (solo mide el enrutador)**
- [ ] Medición de la latencia de `bge-m3` vía Ollama (p50/p95) registrada en ADR-003. — **NO hecho: requiere Ollama corriendo**

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
