# Informe de evaluación — T10

- Fecha: 9 y 10-nov-2026.
- Equipo: ThinkPad i5-8250U (4 núcleos, 8 hilos), 16 GB de RAM, Debian 13, sin GPU. Docker Compose de desarrollo (`infra/docker-compose.yml`), Ollama 0.40.15 en Docker.
- **Todos los datos son SINTÉTICOS o de la pyme de demo "Cocina Los Aromos".** No hay pedidos, documentos, frases ni fotos de una pyme real. Las cifras sirven para comparar alternativas y detectar problemas, no como desempeño con usuarias reales.
- **Condiciones de carga:** las mediciones del 9-nov a la noche se hicieron con varios agentes corriendo a la vez (load average de 7 a 10). El 10-nov, `qwen3:4b` se repitió con la máquina tranquila. La repetición de los demás modelos se cortó para no mezclarla con el trabajo del RAG. Durante la corrida del nivel 2 con LLM, la máquina tenía poca RAM libre (≈ 0,4 GB, 2,4 GB en swap) y un navegador usando CPU: el prefill bajó a ~22 tokens/s (en limpio, ~250). Cada sección indica qué vale.

Cada sección cita el JSON que la respalda y el comando que lo genera.

## 1. Chat sobre documentos (nivel 2, RAG) — `ml/evals/rag/`

**Qué se mide.** Dos cosas distintas:
- **La búsqueda** (`eval_rag.py` → `rag_results.json`): si el fragmento correcto aparece entre los primeros. 9 documentos sintéticos (Markdown, TXT, CSV y un PDF), 50 preguntas con respuesta y 12 sin respuesta (`questions.yaml`).
- **La respuesta que ve la usuaria** (`eval_chat.py` → `chat_results*.json`): cada pregunta pasa por `POST /assistant/ask` en una pyme de prueba nueva. Con respuesta, acierta si el texto mostrado contiene la clave y cita el documento correcto. Sin respuesta, acierta si **no** responde con seguridad desde un fragmento.

```bash
# búsqueda (base propia caterin_eval; nunca la de desarrollo)
docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo \
  -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_eval \
  -e STORAGE_DIR=/tmp/evalstore caterin-api python ml/evals/rag/eval_rag.py
# respuesta de punta a punta, contra la API corriendo (LLM apagado por defecto)
docker run --rm --network container:caterin-api-1 -v "$PWD":/repo:z -w /repo/ml/evals/rag caterin-api \
  python eval_chat.py --questions questions_heldout.yaml --out chat_results_heldout.json
# calibración de la confianza (solo el set de ajuste)
docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo \
  -e DATABASE_URL=postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_eval \
  -e STORAGE_DIR=/tmp/evalstore caterin-api python ml/evals/rag/calibrate_passages.py
```

### 1.1 Búsqueda: comparación de embeddings (`rag_results.json`, 10-nov, fragmentos de ~700 caracteres)

| Variante | recall@1 | recall@5 | MRR | `search` p50 / p95 | Indexar 9 documentos |
|----------|----------|----------|-----|--------------------|----------------------|
| Solo texto (sin vectores) | 0,86 | 1,00 | 0,918 | 5 / 6 ms | 0,5 s |
| `bge-m3` (Ollama) | 0,88 | 1,00 | 0,933 | 154 / 277 ms | 19,1 s |
| `qwen3-embedding:0.6b` | 0,90 | 1,00 | 0,947 | 210 / 351 ms | 29,8 s |
| `qwen3-embedding:0.6b` con instrucción | 0,92 | 1,00 | 0,960 | 521 / 704 ms | 51,4 s |

- **recall@5 está saturado** (17 fragmentos en total): no discrimina. Las diferencias de recall@1 son de 1 a 3 preguntas de 50, no significativas. **Se mantiene `bge-m3`**: es más rápido y `qwen3-embedding` no muestra una mejora clara que compense ser 1,4 a 3,4 veces más lento.
- La variante `sentence-transformers` no se midió aquí: T07 ya midió `bge-m3` por Ollama (62 ms por consulta) frente a `sentence-transformers` (156 ms), con vectores compatibles.
- **Reranker (`bge-reranker-v2-m3`): no evaluado.** No está en Ollama y la imagen de la API no instala PyTorch a propósito. Se dejaron `RAG_DUMP_CANDIDATES=1` en `eval_rag.py` y `rerank_eval.py` (corre fuera de la imagen con `sentence-transformers`) para medirlo; no se alcanzó a correr. Con la indexación por frase (abajo) el problema que quedaba es de sinónimos, donde un cross-encoder sí podría ayudar.

### 1.2 Respuesta de punta a punta: el problema y el cambio

**Problema.** La búsqueda encontraba el documento correcto, pero el nivel 2 sin LLM mostraba **los primeros 350 caracteres** de un fragmento de 700, y la frase que respondía solía venir después. Además, una sola palabra en común ("precio") bastaba para mostrar un fragmento a una pregunta sin respuesta.

**Cambio** (detalle en ADR-005, sección T10): se indexa por **frase** con su contexto; se elige la frase con `similitud + 0,25 × cobertura de términos`, y la **confianza** decide entre responder, mostrar "lo más parecido" con aviso o decir que no está. Si una intención no tiene el dato, se busca en los documentos. Los documentos ya subidos se migran con `python -m app.modules.documents.reindex` (en desarrollo se reindexaron 54).

| Set | Con respuesta: bien (con confianza alta) | Seguras y equivocadas | Sin respuesta: bien (dice "no está" / "no estoy seguro") | Latencia p50 / p95 |
|-----|------------------------------------------|-----------------------|-----------------------------------------------------------|--------------------|
| Ajuste (`questions.yaml`), antes | 27/50 | — | 3/12 | 127 / 149 ms |
| Ajuste, después | **49/50** (41) | **0** | **12/12** (10 / 2) | 118 / 146 ms |
| Reservado (`questions_heldout.yaml`), antes | 20/31 | — | 2/10 | 170 / 306 ms |
| Reservado, después | **28/31** (15) | **2** | **9/10** (4 / 5) | 126 / 153 ms |

- `chat_results_antes.json` y `chat_results_heldout_antes.json` son la línea base (código anterior). "Antes", una pregunta sin respuesta acertaba si no iba al nivel 2; "después", si no responde con confianza alta. En ambos casos, lo que se cuenta como error es mostrar un fragmento como si fuera la respuesta.
- **El set reservado** (41 preguntas nuevas) se escribió antes del cambio y no se usó para ajustar. Lo escribió la misma persona (un agente) que hizo el cambio, sobre los mismos documentos: es una validación débil, aunque honesta.
- **2 respuestas seguras y equivocadas en el set reservado** (detalle en `chat_results_heldout.json`): "¿cuántos limones lleva el pie?" eligió el título del documento, y "¿cuánto le pago a un garzón por evento?" respondió con la hora extra de garzón. Propuesta, a medir con un set reservado **nuevo**: que los títulos no compitan como respuesta cuando solo coinciden en el tema del documento, y revisar el umbral de confianza alta (0,72).
- Fallan las preguntas que necesitan sinónimos o conocimiento externo ("cuesco"/"carozo", "anillos"/"joyas", "Villarrica" ⊂ La Araucanía).
- Se cambió una clave del set de ajuste después de ver resultados: "precio del queso crema en lacteos sur" esperaba la fila cruda de la planilla (`queso crema | 1,5 kg | 9.450`). La respuesta nueva muestra "producto: Queso crema; formato: 1,5 kg; precio_con_iva: 9.450", que es correcta, así que la clave pasó a `9.450`. Está anotado en `questions.yaml`.
- Las corridas crean pymes de prueba ("Eval chat documentos (SINTÉTICA)", usuarias `eval-chat-*@demo.local`) en la base de **desarrollo**; no se borran solas.

<!-- LLM_NIVEL2 -->

## 1b. Preguntas abiertas sobre los datos del negocio (ADR-006) — `ml/evals/assistant/eval_business.py`

**Cambio.** Además de los documentos, el asistente busca por RAG en **fichas del negocio**: una por insumo, receta, proveedor y pedido activo, generadas por código y re-vectorizadas solo cuando cambia su texto. Las **listas** ("¿qué hay en el inventario?", "¿qué lácteos tengo?", "¿qué recetas llevan huevo?") se resuelven completas en código. Los cálculos siguen en las intenciones.

```bash
docker run --rm --network container:caterin-api-1 -v "$PWD":/repo:z -w /repo/ml/evals/assistant caterin-api \
  python eval_business.py --api http://127.0.0.1:8000/api/v1 --questions business_heldout.yaml --out business_heldout_con_llm.json
```

Pyme de demo (sintética). `business_questions.yaml` (22 preguntas) se escribió **antes** de implementar. Después de la primera corrida se corrigieron tres cosas con ese set:
- filtrar por el campo categoría (no por texto, porque "verdu" calzaba con "Verdulería");
- que las palabras de lista no filtren;
- subir el tope de la lista a 40.

Por eso se escribió `business_heldout.yaml` (18 preguntas nuevas) **sin volver a tocar el código**.

| Set | Con respuesta: bien | Sin dato: bien | Seguras y equivocadas | Latencia p50 / máx |
|-----|---------------------|----------------|------------------------|--------------------|
| Ajuste, sin LLM | **18/18** | **4/4** | 0 | 159 / 333 ms |
| Reservado, sin LLM | **13/15** | 2/3 | 1 | 120 / 308 ms |
| Ajuste, con LLM (`qwen3:4b`) | 17/18 (18/18 en revisión manual) | 4/4 | 1 | ver nota |
| Reservado, con LLM | 12/15 (13/15 en revisión manual) | 2/3 | 3 | ver nota |

- **Antes de este cambio, ninguna de estas preguntas tenía respuesta.** La pregunta que lo motivó, "Que elementos existen actualmente dentro del inventario", responde ahora "Tienes 31 insumos: Aceite vegetal (5 L); …" en ~40 ms.
- **Fallos del primer reservado (sin LLM):**
  - "que tipos de pescado hay" y "que abarrotes me quedan": "tipos" y "quedan" quedaban como términos de filtro, la lista salía vacía y la pregunta pasaba al RAG. Las listas dependían de una lista fija de palabras de relleno. **Corregido** (ver "Corrección de las listas").
  - "cuál es el correo de la verdulería": la toma la intención `supplier_info`, que responde los días de despacho. Es una limitación de la intención y sigue sin corregir.

**Corrección de las listas (10-nov).**
- Los términos que van después de "lleva", "usa", "contiene", "incluye", "vende" o "con" son **obligatorios**: si no calzan, no hay lista y la pregunta sigue al RAG. Así, "¿qué recetas llevan nueces?" nunca devuelve todas las recetas.
- El resto de los términos son **opcionales**: filtran solo si calzan con alguna ficha. "tipos" y "quedan" ya no rompen la lista.
- La categoría se reconoce por la palabra o su singular/plural, no por la raíz de 5 letras. Así se corrige una regresión que apareció en el set de ajuste: "dame el rut de la verdulería" listaba las verduras.

Como sale de los fallos del primer reservado, ese set queda gastado. Se escribió `business_heldout2.yaml` (12 preguntas) **antes** de la corrección.

| Set (sin LLM, después de la corrección) | Con respuesta: bien | Sin dato: bien | Seguras y equivocadas |
|------------------------------------------|---------------------|----------------|------------------------|
| Ajuste (`business_questions.yaml`) | 18/18 | 4/4 | 0 |
| Primer reservado (ya gastado) | 15/15 (antes 13/15) | 2/3 | 1 (correo, intención) |
| **Reservado nuevo** (`business_heldout2.yaml`) | **9/9** | 2/3 | 1 |

- En el reservado nuevo, la "segura equivocada" es "qué lácteos llevan las sopaipillas". Se esperaba "no hay dato", pero respondió desde la ficha de alérgenos ("No llevan huevo ni lácteos"), que es **correcto**. La etiqueta del set no lo consideró.
- El chat sobre documentos no retrocedió: 49/50 y 12/12 en el ajuste, y 29/31 y 9/10 en el reservado (`chat_results*.json`).
- **Límite que queda:** la negación ("insumos **sin** precio") no se maneja en las listas.
- **Con LLM:**
  - La comparación exacta de claves no acepta paráfrasis: "bandeja de 500 g", "paquete de 1 kg" están bien en la revisión manual.
  - "que abarrotes me quedan" recibió una **lista parcial** redactada por el LLM. Es el riesgo que motiva las listas en código.
  - 2 respuestas pasaron `LLM_TIMEOUT_S` = 60 s y se mostró la extractiva, que es la degradación esperada.
- **Latencia con LLM: no válida.** El nivel 2 con LLM dio p50 de 45 s con la máquina sobrecargada: poca RAM libre, swap, navegador y las pruebas corriendo a la vez; el prefill bajó a ~22 tokens/s. Hay que medir de nuevo en limpio antes de compararla con la meta de 15 s.
- **Primera pregunta abierta de una pyme:** crea y vectoriza sus fichas (~50 en la demo, ~17 s con la máquina cargada). Las siguientes solo vectorizan las fichas que cambiaron.
- **Sin Ollama**, las fichas se guardan sin vector, la búsqueda queda por texto y la confianza máxima es "baja" (`TEXT_ONLY_LOW_COVERAGE` = 0,8, sin calibrar).

## 1c. Redacción del LLM en el nivel 2 (10-nov) — `ml/evals/assistant/llm_level2_prompts.py`

**Problema visto en uso.** Con `ASSISTANT_USE_LLM=true`, `qwen3:4b` a veces **devolvía la misma pregunta** como respuesta: "¿a quién le compro el salmón?" → "¿a quién le compro el salmón?". Como no traía cifras, el verificador lo dejaba pasar.

**Experimento** con el prompt exacto del asistente y Ollama real, en la pyme de demo (`llm_level2_prompts_r1.json` y `llm_level2_prompts.json`):

| Variante | Con el dato esperado | Eco | Nota |
|----------|----------------------|-----|------|
| A: prompt anterior (pregunta al principio), `qwen3:4b` | 8/10 y 12/15 | 1 | Responde largo; "no lo encontré" para el salmón, aunque la ficha lo dice |
| B: pregunta al final y "no repitas", `qwen3:4b` | 8/10 | 2 | Corrige el salmón; respuestas escuetas ("No", "Especias") |
| C: igual que B, con `qwen3:4b-instruct` | 7/10 | 3 | 3 respuestas vacías: se descarta para esto |
| **D: B más una frase completa y un ejemplo**, `qwen3:4b` | **13/15** | 1 (falso positivo del detector) | "La crema de leche te la vende Distribuidora Ñielol (demo)." |

**Verificación de punta a punta con D** (todos los sets, LLM real). Revisando las respuestas una por una aparecieron **errores graves** que la comparación de claves no veía:
- copió el nombre del ejemplo del prompt ("atienden en concepción" → "La harina te la vende Molino Sur.");
- aplicó la temperatura del refrigerador al helado;
- convirtió "no está en los datos" en un "no" inventado ("¿la harina tiene certificado orgánico?" → "no tiene").

Todos ocurrieron con **confianza baja** en la búsqueda.

**Defensas aplicadas:**
1. **Eco:** si el texto no agrega ninguna palabra a la pregunta, se descarta (`llm_no_answer`) y se muestra la respuesta extractiva. Compara palabras enteras, así que "Las sopaipillas no llevan huevo." no cuenta como eco.
2. **Nombres:** todo nombre propio del texto tiene que estar en los datos (`names_mismatch`).
3. **Prompt:** si los datos no hablan de lo preguntado, el LLM debe responder exactamente "No lo encontré en tus datos.", nunca un "no" inventado. El ejemplo se marca como de formato, con nombres que no debe usar.
4. **Confianza baja:** con confianza baja en la búsqueda, el texto del LLM llega precedido de "No estoy seguro de que esto responda tu pregunta.", salvo que diga que no lo encontró.

**Resultado** (verificación corta con el LLM real, 11 preguntas, incluidas las 4 que fallaban): **11/11 correctas**. Los cuatro casos graves ahora responden "No lo encontré en tus datos." No se repitió la evaluación completa con LLM: para el MVP basta con ~80 % (decisión del usuario, 10-nov). La latencia sigue sin ser válida en esta máquina (5 a 35 s por respuesta).

## 2. Enrutador de intenciones — `ml/evals/assistant/`

- **Set reservado** `heldout.yaml`: 64 frases nuevas, escritas antes de correr nada, incluidas preguntas fuera de alcance, ambiguas e intentos de inyección. **Set dorado** `golden.yaml`: 65 casos, ya usados para afinar en T07.
- `calibrate_router.py` → `calibration.json` barre el umbral (0,40 a 0,90) y el margen (0 a 0,10) con una regla fijada de antemano: el mayor acierto con enrutamiento erróneo ≤ 5 %.

| Umbral / margen | Reservado: acierto | Cobertura | Erróneos | Dorado |
|-----------------|--------------------|-----------|----------|--------|
| 0,65 / 0,03 (provisional de T07) | 49/64 (76,6 %) | 65,6 % | 3 (4,7 %) | 62/65, 0 erróneos |
| **0,55 / 0,10 (adoptado)** | 49/64 (76,6 %) | 62,5 % | **2 (3,1 %)** | 61/65, 0 erróneos |

- La diferencia es de un caso: no es significativa. Se adopta por la regla declarada (`.env.example`, `config.py`, ADR-005).
- **En frases nuevas el acierto es 76,6 %, no el 95 % del set dorado.** Casi todos los fallos son frases de stock o de "lo que me falta" dichas de otra forma, que quedan sin enrutar y piden aclaración (no responden otra cosa). Para mejorar: más ejemplos en `intents.yaml` y un set reservado **nuevo**, idealmente con frases reales.

## 3. Cobertura de pruebas de la API

`pytest --cov` dentro del contenedor de la API (10-nov): **96 % en total**, con 215 pruebas que pasan. Después del RAG por frase y de las fichas del negocio (10-nov): **238 pruebas que pasan y 1 `xfail`**, con lint y tipos limpios, y **96 %** de cobertura total. Los módulos nuevos están entre 96 y 100 %: `knowledge/cards.py` 96 %, `knowledge/service.py` 97 %, `knowledge/lists.py` 100 %, `documents/sentences.py` 100 % y `assistant/passages.py` 99 %.

| Módulo | Cobertura | Meta |
|--------|-----------|------|
| `recipes/costing.py` | 99 % | ≥ 80 % ✔ |
| `quotes/calculator.py` | 99 % | ≥ 80 % ✔ |
| `core/units.py` | 98 % | ≥ 80 % ✔ |
| `assistant/verifier.py` (verificador de cifras) | 100 % | ≥ 80 % ✔ |
| Resto de la API | 96 % | ≥ 60 % ✔ |

El módulo con menos cobertura es `quotes/evaluation.py` (75 %), que es el arnés de evaluación del extractor, no código del producto.

## 4. E2E del MVP (Playwright)

`apps/web/e2e/mvp.e2e.ts`: una usuaria nueva se registra, crea insumos, precios y una receta, cotiza y descarga el PDF. Son 28 toques, 23 campos y 10 pantallas. Según el commit c52ee24 (9-nov), pasan 8 e2e (`pwa.e2e.ts` se corre aparte contra `vite preview`) y Vitest 70/70, y axe no reporta violaciones serias. **No se repitió el 10-nov**; los cambios del 10-nov no tocan `apps/web`.

## 5. Carga ligera (Locust) — `ml/evals/load/`

Perfil mixto, 5 usuarias × 5 min, API con `ASSISTANT_USE_LLM=false` (`results/mix_stats.csv`, 9-nov, **máquina cargada por otros agentes**): **754 requests, 0 fallos**, p50 21 ms y p95 94 ms en el agregado.

| Endpoint | n | p50 | p95 |
|----------|---|-----|-----|
| `assistant/ask` (nivel 0) | 233 | 59 ms | 89 ms |
| `orders/{id}/quotes` (cotizar) | 57 | 84 ms | 130 ms |
| `ingredients` | 186 | 12 ms | 22 ms |
| `vision/count` | 45 | 8 ms | 26 ms |

- **`vision/count` no mide inferencia:** en esta máquina el detector no carga (falta `model.json` del modelo de prueba de T06) y responde 503, que el locustfile contaba como éxito. Además mandaba un PNG de 1×1. Se cambió para usar una foto JPEG (`bandeja.jpg`, del split de test sintético; no se commitea). Hay que repetir la medición con el modelo.
- **Perfil con LLM: no completado** (la corrida se cortó). Pendiente: 3 usuarias × 2 min con `LOAD_PROFILE=llm` contra una instancia con `ASSISTANT_USE_LLM=true`, para ver la cola de Ollama.

## 6. LLM y extractor

Ver ADR-003, sección T10. En resumen:
- `qwen3:4b`, medido en limpio: 7,1 tokens/s, llega al tope de 160 tokens y filtra razonamiento en inglés en 12/12 respuestas de texto libre (la app lo evita con salida JSON).
- `qwen3:4b-instruct`, medido con la máquina cargada: 0/12 con razonamiento colado, tool calling 4/4 y extracción 8/8.
- Gemma 4 E4B y la evaluación del extractor con los 20 pedidos reservados (`ml/evals/extractor/cases.yaml`, escritos antes de correr ningún modelo) **no alcanzaron a correr**. Comandos:

```bash
for m in qwen3:4b-instruct gemma4:e4b; do
  docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo/ml/bench caterin-api \
    python bench_cpu.py --out bench_results_t10.json llm --models $m --host http://ollama:11434 --repeats 3
done
docker run --rm --network caterin_default -v "$PWD":/repo:z -w /repo caterin-api \
  python ml/evals/extractor/eval_extractor.py --models qwen3:4b qwen3:4b-instruct gemma4:e4b \
  --cases ml/evals/extractor/cases.yaml --out ml/evals/extractor/results_t10.json
```

La referencia del extractor sigue siendo la de T05: `qwen3:4b`, 188/193 campos (97,4 %) en 22 pedidos sintéticos ya usados (`results.json`).

## 7. Redacción (revisión humana)

`rubric.md` (corrección, claridad y tono chileno, de 1 a 3) y `review_sheet.csv` (22 respuestas de nivel 1 y 2 de `qwen3:4b`, generadas con `make_review_sheet.py`). **Falta que 2 personas del equipo la llenen.** Sin eso, `ASSISTANT_USE_LLM` sigue en `false` por defecto. Umbral propuesto para encenderlo: corrección ≥ 2,8 sin ninguna nota 1, y claridad y tono ≥ 2,5.

## 8. Visión

**No cumplido.** No hay fotos reales de una pyme y el modelo de prueba de T06 (Snacks) no está en esta máquina. No hay mAP por clase, matriz de confusión con datos reales, curva de aprendizaje real, umbral objetivo ni latencia con JPEG de celular en el VPS. Lo que existe está en `ml/vision/MODEL_CARD.md`.

## 9. Pendiente y próximos pasos

1. Con la máquina tranquila (sin navegador pesado y con RAM libre), correr los comandos de la sección 6, el perfil de carga con LLM y `ml/evals/assistant/eval_assistant.py`, que corre los 129 casos dorados y reservados por la API con el LLM encendido y mide nivel, cifras descartadas y latencia.
2. Revisión humana de la redacción (sección 7).
3. Reranker (`rag/rerank_eval.py`, fuera de la imagen).
4. Un set reservado **nuevo** para el nivel 2 y otro para el enrutador, idealmente con preguntas y documentos reales de una emprendedora (pregunta 6 del índice), para medir los arreglos propuestos sin sesgo.
5. Visión con fotos reales.
