# T10 — Calidad y evaluaciones
- Estado: en curso
- Depende de: T05, T06, T07
- Funcionalidad: transversal

## Objetivo
Saber, con evidencia propia, que los números son correctos, que el asistente no inventa y que los modelos elegidos son los adecuados, antes de ponerlo en manos de una emprendedora.

## Contexto y decisiones previas
- ADR-003 (pruebas pendientes) y ADR-005 (calibración del umbral).
- Tabla de evaluación de `AGENTS.md`, sección 3.1.
- **El script de benchmark del repo (`main.py`, que se mueve a `ml/bench/bench_cpu.py` en T01) no tiene las correcciones que cita `AGENTS.md`** (ADR-003, "Límites y problemas detectados"). Si el equipo no tiene la versión corregida, se corrige aquí.

## Entregables
- [x] **Benchmark corregido:** RAM por nombre exacto del modelo en `/api/ps`, `eval_count` por respuesta (tokens generados), detalle de qué campo falló en la extracción y versión del script en el JSON de salida.
- [ ] Repetir `llm` con `qwen3:4b`, `qwen3:4b-instruct` y Gemma 4 E4B (verificando los tags) y actualizar ADR-003 y `AGENTS.md`, sección 3.1.
- [ ] **Asistente:** set dorado de 40 a 60 casos en `ml/evals/assistant/` (intenciones formuladas de varias maneras, sin dato, ambiguas, inyección). Métricas: acierto del enrutador por nivel, exactitud de los datos, cifras de la redacción presentes en la entrada, tasa de alucinación, latencia p50/p95 por nivel, tokens generados y RAM.
- [ ] **Redacción:** rúbrica de revisión humana (1 a 3 en corrección, claridad y tono chileno natural), con al menos 2 revisores del equipo por respuesta.
- [x] **Calibración del umbral del enrutador** (curva de precisión y cobertura); el valor elegido queda en ADR-005 y en `.env.example`.
- [ ] **Extractor:** ≥ 20 pedidos (sintéticos y, si es posible, reales anonimizados), exactitud campo a campo.
- [ ] **RAG:** ≥ 50 preguntas sobre documentos realistas; recall@5 y MRR; `bge-m3` (Ollama) frente a `sentence-transformers` y `Qwen3-Embedding-0.6B`; con y sin reranker.
- [ ] **Visión:** evaluación en el split de test (mAP, error de conteo, latencia de punta a punta). Viene de T06, que dejó el pipeline y un modelo de **prueba** (Snacks); con fotos reales de una pyme falta: reentrenar (`ml/vision/train.py`), mAP50 y mAP50:95 por clase, matriz de confusión, curva de aprendizaje, fijar el umbral objetivo de precisión en `ml/vision/MODEL_CARD.md`, y repetir la latencia con JPEG de celular y en el VPS. Sin fotos reales se reporta como no cumplido.
- [x] **Cobertura mínima:** ≥ 80% en `recipes/costing.py`, `quotes/calculator.py`, `core/units.py` y el verificador de cifras; ≥ 60% en el resto de la API (propuesta).
- [x] **E2E** con Playwright de los criterios globales del MVP (`AGENTS.md`, sección 9).
- [ ] **Carga ligera:** p. ej. 5 usuarias concurrentes durante 5 minutos (k6 o Locust) mezclando consultas de nivel 0, cotizaciones y fotos; ver cómo se comporta el LLM en cola.
- [x] Informe `ml/evals/REPORT.md` con los resultados, el equipo usado, la fecha y los límites.

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

## Avance (10-nov-2026)

Detalle en `ml/evals/REPORT.md`. Todo con datos **sintéticos**.

- **Hecho:**
  - benchmark corregido (`bench_cpu.py` 2.0.0);
  - umbral del enrutador calibrado con el set reservado (0,55 / 0,10);
  - cobertura de la API en 96 % (los módulos críticos, entre 98 y 100 %);
  - e2e del MVP con Playwright;
  - carga mixta: 5 usuarias × 5 min, 754 requests, 0 fallos, nivel 0 p95 89 ms;
  - comparación de embeddings con 50 preguntas;
  - rúbrica y planilla de revisión humana.
- **Hecho, fuera del plan original:** el chat sobre documentos (nivel 2) **no respondía bien** aunque la búsqueda encontrara el documento: 27/50 preguntas bien respondidas. Se cambió a indexación por frase, con respuesta extractiva con confianza y reindexación de los documentos antiguos. Quedó en 49/50 en el set de ajuste y 28/31 en un set reservado escrito antes del cambio, con 2 respuestas seguras equivocadas en el reservado. Ver ADR-005.
- **Parcial:**
  - LLM: `qwen3:4b` medido en limpio; `qwen3:4b-instruct` medido con la máquina cargada; Gemma 4 E4B sin medir.
  - Asistente de punta a punta con LLM (`eval_assistant.py`, escrito, sin correr).
  - Carga con LLM (cortada).
- **Pendiente:**
  - extractor con 20 pedidos reservados y 3 modelos (`eval_extractor.py`, listo);
  - reranker (`rerank_eval.py`, listo);
  - revisión humana de la redacción (2 personas del equipo);
  - visión (sin fotos reales y sin el modelo de prueba en esta máquina: **no cumplido**).

### Decisión del usuario (10-nov-2026): RAG sobre los datos del negocio

Las intenciones fijas se quedan cortas ("¿qué elementos hay en el inventario?" no tiene intención y no se responde). Se decidió pasar a **RAG sobre fichas del negocio más cálculos en código**:
- una ficha de texto por insumo, receta, proveedor y pedido, con sus valores actuales, en pgvector junto a los documentos, y re-vectorizada al cambiar el dato (`data_version`);
- el LLM responde por RAG las preguntas abiertas, citando la ficha, y el verificador de cifras sigue activo;
- las listas y los totales los arma un filtro en código;
- los costos y la factibilidad siguen calculados en código. Las intenciones quedan como atajo rápido.

Esto cambia la regla de `AGENTS.md` ("datos estructurados … no se vectorizan") y requiere **ADR-006** antes de implementar. Todavía no está implementado.

Estado local al subir: en el `.env` de desarrollo de quien subió el cambio se activó `ASSISTANT_USE_LLM=true`. El valor por defecto en `.env.example` y `config.py` sigue en `false`. La pyme de demo de esa base tiene los 9 documentos sintéticos de `ml/evals/rag/docs` cargados.

Verificado antes de subir (10-nov): `ruff check`, `ruff format --check` y `mypy app` limpios; `pytest -m "not llm"`: 227 pasan y 1 es un fallo esperado (`xfail`).

## Resumen de cierre
(se completa al terminar)
