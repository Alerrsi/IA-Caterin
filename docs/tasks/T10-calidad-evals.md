# T10 — Calidad y evaluaciones
- Estado: pendiente
- Depende de: T05, T06, T07
- Funcionalidad: transversal

## Objetivo
Saber, con evidencia propia, que los números son correctos, que el asistente no inventa y que los modelos elegidos son los adecuados, antes de ponerlo en manos de una emprendedora.

## Contexto y decisiones previas
- ADR-003 (pruebas pendientes) y ADR-005 (calibración del umbral).
- Tabla de evaluación de `AGENTS.md`, sección 3.1.
- **El script de benchmark del repo (`main.py`, que se mueve a `ml/bench/bench_cpu.py` en T01) no tiene las correcciones que cita `AGENTS.md`** (ADR-003, "Límites y problemas detectados"). Si el equipo no tiene la versión corregida, se corrige aquí.

## Entregables
- [ ] **Benchmark corregido:** RAM por nombre exacto del modelo en `/api/ps`, `eval_count` por respuesta (tokens generados), detalle de qué campo falló en la extracción y versión del script en el JSON de salida.
- [ ] Repetir `llm` con `qwen3:4b`, `qwen3:4b-instruct` y Gemma 4 E4B (verificando los tags) y actualizar ADR-003 y `AGENTS.md`, sección 3.1.
- [ ] **Asistente:** set dorado de 40 a 60 casos en `ml/evals/assistant/` (intenciones formuladas de varias maneras, sin dato, ambiguas, inyección). Métricas: acierto del enrutador por nivel, exactitud de los datos, cifras de la redacción presentes en la entrada, tasa de alucinación, latencia p50/p95 por nivel, tokens generados y RAM.
- [ ] **Redacción:** rúbrica de revisión humana (1 a 3 en corrección, claridad y tono chileno natural), con al menos 2 revisores del equipo por respuesta.
- [ ] **Calibración del umbral del enrutador** (curva de precisión y cobertura); el valor elegido queda en ADR-005 y en `.env.example`.
- [ ] **Extractor:** ≥ 20 pedidos (sintéticos y, si es posible, reales anonimizados), exactitud campo a campo.
- [ ] **RAG:** ≥ 50 preguntas sobre documentos realistas; recall@5 y MRR; `bge-m3` (Ollama) frente a `sentence-transformers` y `Qwen3-Embedding-0.6B`; con y sin reranker.
- [ ] **Visión:** evaluación en el split de test (mAP, error de conteo, latencia de punta a punta).
- [ ] **Cobertura mínima:** ≥ 80% en `recipes/costing.py`, `quotes/calculator.py`, `core/units.py` y el verificador de cifras; ≥ 60% en el resto de la API (propuesta).
- [ ] **E2E** con Playwright de los criterios globales del MVP (`AGENTS.md`, sección 9).
- [ ] **Carga ligera:** p. ej. 5 usuarias concurrentes durante 5 minutos (k6 o Locust) mezclando consultas de nivel 0, cotizaciones y fotos; ver cómo se comporta el LLM en cola.
- [ ] Informe `ml/evals/REPORT.md` con los resultados, el equipo usado, la fecha y los límites.

## Criterios de aceptación
- Todos los scripts de evaluación corren con un comando documentado y escriben resultados versionados (JSON) que el informe cita.
- ADR-003 pasa a "aceptado" con la elección final por componente, o explica por qué sigue provisional.
- Las métricas que no alcanzan su umbral se reportan tal cual, con alternativas propuestas.

## Pruebas requeridas
- Las de esta tarea son, en sí mismas, la evaluación. El CI corre las unitarias y las de integración rápidas; las evaluaciones con modelos reales se corren a mano o en un job aparte.

## Fuera de alcance
- Evaluación de `qwen3:8b`/`14b` para el nivel 3, salvo que haya GPU o proveedor externo disponible.

## Riesgos y preguntas abiertas
- El equipo de referencia se ralentizó durante la primera ronda: repetir con el cargador conectado, sin otros procesos pesados, y anotar la temperatura o el *throttling* si se puede.
- La revisión humana de la redacción toma tiempo; reservarlo en la planificación.

## Resumen de cierre
(se completa al terminar)
