# ADR-003 — Modelos de IA

- Estado: **propuesto, ratificación parcial** (9-nov-2026; licencias verificadas en T01). Se ratifica del todo cuando T10 termine la evaluación con casos propios.
- Contexto en: `AGENTS.md` sección 3.1
- Fuente de los datos medidos: `bench_results.json` (9-nov-2026), generado con `ml/bench/bench_cpu.py` (antes `main.py` en la raíz).

## Contexto

Necesitamos modelos con licencia permisiva que corran en hardware barato (CPU de VPS) y anden bien en español, para tres usos:

1. **LLM:** redactar respuestas del asistente (F1, niveles 1 y 2) y extraer pedidos (F3).
2. **Embeddings y reranker:** el enrutador de intenciones y el RAG de F1.
3. **Detector:** contar productos finales en una foto (F2).

## Decisión por componente

| Componente | Modelo elegido | Estado | Condición para cambiarlo |
|------------|----------------|--------|--------------------------|
| LLM por defecto (redactar y extraer) | `qwen3:4b` en Ollama, thinking desactivado | **Ratificado provisionalmente** | Que `qwen3:4b-instruct` o Gemma 4 E4B sean mejores en la evaluación de T10 (redacción en español de Chile y extracción campo a campo) sin empeorar tokens/s |
| LLM nivel 3 (agente, opcional) | `qwen3:8b` | Apagado por defecto | Solo con GPU o proveedor externo |
| Embeddings | `BAAI/bge-m3` (1024 dimensiones) | **Ratificado provisionalmente** | Que `Qwen3-Embedding-0.6B` muestre una mejora clara de recall@5/MRR con documentos reales que compense ser ~5 veces más lento |
| Reranker | `BAAI/bge-reranker-v2-m3` | **Apagado por defecto** | Se enciende si mejora recall@5 en T10, y solo sobre ≤ 10 candidatos |
| Detector | RF-DETR Nano → ONNX | **Ratificado provisionalmente** (solo latencia) | Pasar a Small si la precisión no alcanza; RT-DETRv2 o D-FINE si es muy lento en el VPS |

### Decisión adicional: los embeddings se sirven con Ollama

El benchmark midió `bge-m3` con `sentence-transformers` (PyTorch). En producción se propone servirlo con **Ollama** (`ollama pull bge-m3`, endpoint `/api/embed`) para no instalar PyTorch en la imagen de la API (varios GB) y reusar el servicio que ya existe.

- **Riesgo:** la latencia y los vectores pueden diferir de lo medido (otra cuantización, solo vectores densos). **No está medido.** T07 lo mide y T10 lo compara. Si empeora el recall o la latencia de forma clara, se usa ONNX Runtime con el modelo exportado.
- El reranker no está en Ollama. Como está apagado por defecto, se decide cómo servirlo solo si T10 justifica encenderlo.

## Resultados del benchmark propio

Equipo: ThinkPad i5-8250U (4 núcleos, 8 hilos), 16 GB de RAM, Debian 13, sin GPU. El equipo se ralentizó de forma intermitente durante las pruebas.

### LLM (Ollama, `temperature` 0.1, `num_ctx` 4096, `num_predict` 160, `think: false`)

| Modelo | Tokens/s p50 | Prefill p50 | Latencia total p50 / p95 (n=12) | Carga | Tool calling | Extracción |
|--------|--------------|-------------|---------------------------------|-------|--------------|------------|
| `qwen3:4b` | 7.5 | 1.2 s | 22.7 s / 26.1 s | 7.4 s | 1/4 | 7/8 campos |
| `qwen3:8b` | 4.3 | 2.73 s | 11.1 s / 25.2 s | 31.8 s | 4/4 | 7/8 campos |

### Embeddings y reranker (`sentence-transformers`, CPU)

| Modelo | Consulta p50 / p95 | 12 pasajes | recall@1 / recall@3 / MRR |
|--------|--------------------|------------|---------------------------|
| `BAAI/bge-m3` | 156 / 235 ms | 2.78 s | 1.0 / 1.0 / 1.0 |
| `Qwen/Qwen3-Embedding-0.6B` | 807 / 912 ms | 12.1 s | 1.0 / 1.0 / 1.0 |
| `bge-reranker-v2-m3` | 817 ms (5 candidatos), 3696 ms (20) | — | sin cambio |

### Detector (ONNX Runtime, CPU)

| Modelo | Entrada | p50 / p95 | FPS p50 | Carga |
|--------|---------|-----------|---------|-------|
| RF-DETR Nano (`output/rfdetr-nano.onnx`, 115 MB) | 1×3×384×384 | 169 / 199 ms | 5.9 | 0.6 s |

### Extractor de pedidos con el flujo real de la API (T05, 9-nov-2026)

`qwen3:4b`, prompt `extract-v1`, JSON schema, `think: false`, 22 pedidos sintéticos (`ml/evals/extractor/`): **188/193 campos (97,4 %)**, 18/22 pedidos perfectos, 0 JSON inválidos, latencia del LLM p50 13,7 s y p95 22,0 s, 89 tokens (p50). Dos de los cinco fallos fueron **cantidades cambiadas por el modelo** (200 → 201, 50 → 100): por eso el extractor tiene una barrera en código que marca cualquier cantidad que no aparezca en el mensaje.

## Límites y problemas detectados en el benchmark

Revisión del script en `main.py` hecha al escribir este ADR:

1. **El script no es la versión corregida.** `AGENTS.md` dice que `bench_cpu.py` ya corrige el bug de RAM y registra tokens y fallos, pero el archivo del repo (`main.py`) todavía:
   - Calcula la RAM con `m["name"].startswith(model.split(":")[0])`. Con `qwen3:4b` y `qwen3:8b` ambos empiezan con `qwen3`, así que la cifra puede ser la del otro modelo cargado. Eso explica el 3.2 GB idéntico en los dos. **El dato de RAM no vale.**
   - No guarda `eval_count` (tokens generados) por respuesta, así que la latencia total no se puede comparar entre modelos.
   - En la extracción no registra qué campo falló (solo `campos_ok`/`campos_total`).

   Puede que la versión corregida exista en otro equipo y no se haya copiado. **Pregunta abierta para el equipo.** Si no existe, la corrección se hace en T10 (el script pasa a `ml/bench/bench_cpu.py` en T01).
2. **La latencia total no sirve para comparar modelos**, por lo de los tokens generados.
3. **El test de embeddings está saturado** (12 pasajes sintéticos, todos aciertan). No discrimina entre modelos.
4. **Tool calling y extracción tienen muy pocos casos** (4 y 3 textos). Sirven para descartar, no para fijar porcentajes.
5. **El detector se midió con una imagen aleatoria**, sin decodificación, preprocesamiento ni postprocesamiento, y sin medir precisión.
6. El benchmark se corrió con Python 3.13.5; el stack fija 3.12. No debería afectar la latencia de Ollama ni de ONNX, pero se anota.

## Verificación de licencias

**Verificado el 9-nov-2026 (T01)** en los metadatos de la model card (API de Hugging Face, campo `license`) y en el repositorio oficial de RF-DETR. Los tags de Ollama se verificaron en el registro `registry.ollama.ai`. Detalle en `THIRD_PARTY_NOTICES.md` y `models.lock.yaml`.

| Modelo | Licencia verificada | Fuente | Nota |
|--------|---------------------|--------|------|
| `qwen3:4b`, `qwen3:8b` | Apache 2.0 | `Qwen/Qwen3-4B` (rev. 1cfa9a720891), `Qwen/Qwen3-8B` (rev. b968826d9c46) | ✔ |
| `qwen3:4b-instruct` | Apache 2.0 (familia Qwen3) | El tag **existe** en el registro de Ollama | ✔ el tag; los pesos exactos se anotan al descargarlo |
| Gemma 4 E4B (`gemma4:e4b`) | Apache 2.0 | `google/gemma-4-E4B-it` (rev. 4ecc2ba63bca); el tag existe en Ollama | ✔ A diferencia de Gemma 3, sí es Apache 2.0 |
| `BAAI/bge-m3` | MIT | rev. 5617a9f61b02; el tag `bge-m3` existe en Ollama | ✔ |
| `BAAI/bge-reranker-v2-m3` | **Apache 2.0** | rev. 953dc6f6f85a | ✔ AGENTS.md decía "permisiva" sin precisar |
| `Qwen/Qwen3-Embedding-0.6B` | Apache 2.0 | rev. 97b0c614be4d | ✔ |
| RF-DETR Nano, Small, Medium, Large | Apache 2.0 | `LICENSE` y README de `roboflow/rf-detr` | ✔ **Corrección:** además de XL y 2XL, también Atto, Femto y Pico son PML 1.0 (paquete `rfdetr[plus]`); no se usan |
| Backbone DINOv2 de RF-DETR | Incluido en el paquete `rfdetr` bajo Apache 2.0 según su README | — | Revisar de nuevo al ajustar el modelo en T06 |

Límite de esta verificación: se leyó el campo de licencia de los metadatos y el README, no el texto legal completo de cada licencia.

## Configuración base del LLM

- `temperature`: 0.1 para extraer y 0.2 para redactar.
- `think: false` por defecto.
- `num_ctx`: 4096. `num_predict`: 120 para redactar y 300 para extraer (el JSON necesita más espacio).
- Prefijo fijo (mensaje de sistema y formato) para que Ollama reutilice la caché de prefijo.
- `keep_alive` largo (p. ej. 30 min o `-1` en producción) para no pagar los 7.4 s de carga en cada consulta.
- Extracción con `format` = JSON schema generado desde el modelo Pydantic.

## Medido en T07 (9-nov-2026, equipo de referencia i5-8250U, Ollama 0.40.15 en Docker)

- **`bge-m3` servido por Ollama** (`/api/embed`): consulta de una frase p50 **62 ms**, p95 **70 ms** (n = 20), 12 pasajes en 3,5 s y primera llamada 5,2 s (carga del modelo). Más rápido que los 156 ms de `sentence-transformers`; vectores de 1024 dimensiones, como fija la migración. Se ratifica servirlo con Ollama.
- **`qwen3:4b` mezcla su razonamiento con la respuesta en *streaming*.** La ficha del tag en este Ollama dice *thinking* por defecto y contexto de 262144. Con `think: false`, Ollama deja de separar el campo `thinking`, pero el modelo igual escribe su razonamiento **en inglés** dentro del texto ("Okay, let's see. The user is asking…"). El verificador de cifras no lo detecta, porque solo repite números del dato. **Mitigación aplicada:** `chat_stream` también pide salida JSON (`{"respuesta": "..."}`) y entrega el valor a medida que llega; con la gramática no hay espacio para el razonamiento. Así, las respuestas medidas salieron limpias y en español, de unos 40 tokens.
- Esto refuerza la evaluación pendiente de **`qwen3:4b-instruct`** (variante sin *thinking*): si redacta igual de bien, evita depender de la gramática JSON para que no se cuele el razonamiento.
- Latencia de punta a punta del asistente por nivel: ver ADR-005 y `ml/evals/assistant/bench_levels.json`.

## Pruebas pendientes (las ejecuta T10)

1. Corregir el script (RAM por nombre exacto, tokens generados, detalle de fallos) y repetir `llm` con `qwen3:4b`, `qwen3:4b-instruct` y Gemma 4 E4B, con más casos de extracción (≥ 20).
2. Agregar la evaluación de redacción en español de Chile con revisión humana (rúbrica en T10).
3. ~~Medir `bge-m3` servido por Ollama frente a `sentence-transformers`.~~ Hecho en T07 (arriba).
4. Repetir embeddings con ≥ 50 preguntas sobre documentos reales o sintéticos realistas, con y sin reranker.
5. Calibrar el umbral del enrutador de intenciones (ADR-005).
6. Medir el detector de punta a punta (decodificar JPEG, preprocesar, inferir, postprocesar) con el modelo ajustado y en el VPS objetivo.

## Consecuencias

- `models.lock.yaml` fija el identificador, la revisión, la licencia, el tamaño y el sha256 (de los ONNX) de cada modelo. Un script verifica que coincidan (T01).
- Los pesos **no se commitean**. `output/rfdetr-nano.onnx` (115 MB) se agrega a `.gitignore` en T01.
- Cambiar cualquier modelo exige actualizar este ADR y `models.lock.yaml`.
