# T07 — Asistente por niveles con RAG
- Estado: pendiente
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
- [ ] `intents.yaml` con el catálogo inicial de ADR-005 (≥ 8 ejemplos por intención, en español de Chile) y su validación al cargar.
- [ ] Enrutador: reglas y palabras clave → similitud con `bge-m3` (embeddings de los ejemplos precalculados al iniciar) → umbral y margen.
- [ ] Resolución de entidades con `rapidfuzz` y fechas relativas en español de Chile (`America/Santiago`).
- [ ] Consultas tipadas de solo lectura (reusan los servicios de T04/T05) y plantillas de nivel 0.
- [ ] `core/llm`: `LLMProvider` con Ollama (*streaming*, timeout, `keep_alive`) y la interfaz para un proveedor externo opcional.
- [ ] Nivel 1: redacción con dato compacto, verificación de cifras y degradación a plantilla.
- [ ] Nivel 2: subida de documentos (PDF, XLSX, CSV, TXT), *chunking*, embeddings, búsqueda híbrida (pgvector + FTS `spanish`, fusión por RRF), 3 a 5 fragmentos, citas. Reranker detrás de un flag, apagado.
- [ ] Caché por pyme con `data_version` (ADR-005).
- [ ] `POST /assistant/ask` en SSE y JSON, `GET /assistant/quick-actions`, `POST /assistant/feedback`, `/documents`.
- [ ] Registro completo en `assistant_interaction`.
- [ ] Defensas contra prompt injection (SECURITY, sección 3).
- [ ] Set dorado inicial en `ml/evals/assistant/` (≥ 40 casos: preguntas de gestión formuladas de varias maneras, sin dato, ambiguas, inyección) y un script que mide el acierto del enrutador por nivel.
- [ ] Medición de la latencia de `bge-m3` vía Ollama (p50/p95) registrada en ADR-003.

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

## Resumen de cierre
(se completa al terminar)
