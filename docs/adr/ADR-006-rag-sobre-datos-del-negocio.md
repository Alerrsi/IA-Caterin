# ADR-006 — RAG sobre los datos del negocio (fichas) y cálculos en código

- Estado: **aceptado** (10-nov-2026, decisión del usuario). Modifica una regla de `AGENTS.md` (sección 4, F1) y amplía ADR-005.
- Contexto en: ADR-002 (cálculo determinista), ADR-005 (asistente por niveles), T10.

## Contexto

Con ADR-005, el asistente responde los datos de la pyme solo con **intenciones fijas**: nueve consultas tipadas con plantilla. Los documentos subidos pasaban por RAG, pero `AGENTS.md` prohibía vectorizar los datos estructurados: "Datos estructurados (stock, costos, pedidos) se consultan por funciones, no se vectorizan".

En la práctica, esto dejó al asistente **demasiado básico**:
- "¿Qué elementos existen actualmente dentro del inventario?" no tenía intención y terminaba en "No estoy seguro de qué me preguntas".
- Lo mismo con "¿qué lácteos tengo?", "¿qué recetas llevan huevo?" o "¿quién me vende la crema?".

Cada pregunta nueva exigía programar una intención. El usuario pidió que el asistente consulte los datos del negocio por RAG sobre la base vectorial, como hace con los documentos.

Los motivos de la regla original siguen siendo válidos y se mantienen donde importan:
- Un LLM de 4B se equivoca con los números.
- El RAG solo trae unos pocos resultados, así que no sirve para listas completas ni totales.
- Un vector viejo da datos desactualizados.

## Decisión

1. **Fichas del negocio** (`knowledge_card`): una ficha de texto por insumo, receta, proveedor y pedido activo, con sus valores actuales. Por ejemplo: "Insumo: Queso crema. Categoría: Lácteos y huevos. Stock: 2 kg (mínimo 500 g). Precios vigentes: Distribuidora Ñielol, pote 1 kg a $7.490 (03/11/2026)."
   - Se vectoriza con `bge-m3` en pgvector, en la misma base y con la misma dimensión que los documentos.
   - Cada ficha tiene búsqueda de texto completo sin tildes.
   - El texto lo arma **código**, desde la base. Las cifras son las guardadas, sin cálculos del LLM.
2. **Sincronización incremental y perezosa** (`knowledge_sync`):
   - Antes de buscar, se compara la `data_version` de cada dominio con la última sincronizada.
   - Si cambió, se regeneran los textos de las fichas afectadas y **solo se vuelven a vectorizar las fichas cuyo texto cambió** (por hash).
   - Las fichas de entidades borradas o inactivas se eliminan.
   - Si los embeddings no están disponibles, la ficha queda buscable por texto.
3. **Listas y filtros en código** (`knowledge/lists.py`): "¿qué hay en el inventario?", "¿qué lácteos tengo?", "¿qué recetas llevan huevo?", "¿cuántos proveedores tengo?".
   - Se detecta en código que se pide una lista: tipo de entidad o categoría, más una palabra de lista.
   - Se filtran **todas** las fichas de ese tipo por los términos de la pregunta y se responde con el total exacto y los nombres. Sin LLM.
4. **RAG sobre fichas y documentos** para las preguntas abiertas que no son ni intención ni lista.
   - La búsqueda híbrida trae candidatas de los dos lados. La respuesta extractiva y su confianza (ADR-005, `passages.py`) eligen entre ellas.
   - Con `ASSISTANT_USE_LLM=true`, el LLM redacta con las fichas y fragmentos recuperados y cita la fuente. El verificador de cifras sigue activo.
5. **Los cálculos siguen en código** (ADR-002): el costo de una receta, si alcanza el stock para un pedido, el mejor precio y los totales. Las intenciones quedan como **atajo** rápido y exacto para esas preguntas, no como límite de lo que se puede preguntar.

Orden en el asistente: intención reconocida → (si no hay dato) documentos y fichas → lista → RAG sobre fichas y documentos → "no lo encontré".

## Cambio en `AGENTS.md`

La regla "Datos estructurados (stock, costos, pedidos) se consultan por funciones, no se vectorizan" pasa a ser:
- Los **cálculos** y las **listas completas** se resuelven por funciones.
- Los datos del negocio se vectorizan además como **fichas de texto generadas por código**, para el RAG de preguntas abiertas.

## Consecuencias

- **Más preguntas sin programar intenciones**, con fuente visible ("según tu inventario: Queso crema").
- **Costo:**
  - Vectorizar fichas: una vez por pyme (unas 50 fichas en la demo) y después solo las que cambian, con ~60 a 100 ms cada una en CPU.
  - Una búsqueda más por pregunta abierta.
  - Las listas no usan LLM.
- **Datos personales:** las fichas de pedidos incluyen el nombre del cliente, pero no su contacto (`customer_contact` queda fuera). Con Ollama local nada sale del servidor. Con un proveedor externo de LLM, esos nombres se enviarían en el prompt, así que hay que configurarlo y documentarlo (`SECURITY.md`).
- **Multi-tenant:** `knowledge_card` y `knowledge_sync` llevan `pyme_id` y pasan por el filtro central de tenant. Hay pruebas de que una pyme no ve las fichas de otra.
- **Riesgo de dato desactualizado:** la sincronización corre antes de cada búsqueda. Una escritura que no incremente `data_version` dejaría la ficha vieja. Las escrituras de inventario, recetas, proveedores y pedidos ya lo incrementan (T07).
- **Filtros de las listas:**
  - Lo que va después de "lleva", "usa", "contiene", "incluye", "vende" o "con" es obligatorio.
  - El resto filtra solo si calza con alguna ficha.
  - La categoría se reconoce por la palabra o su singular/plural.
  - La negación ("sin precio") no se maneja.
- **Límites:** el RAG sobre fichas sigue trayendo pocas fichas. Una pregunta de lista que el detector no reconozca recibe una respuesta parcial (con LLM, una lista incompleta). Se mide con `ml/evals/assistant/business_*.yaml` (`eval_business.py`, resultados en `ml/evals/REPORT.md`, sección 1b).

## Redacción del LLM sobre fichas y documentos (T10, 10-nov)

- **Prompt del nivel 2:** datos primero y pregunta al final, una frase completa y un ejemplo de formato. Si no hay dato, responde exactamente "No lo encontré en tus datos.".
- **Verificaciones del texto del LLM:**
  - cifras (ADR-002);
  - eco de la pregunta (`llm_no_answer`);
  - nombres propios que no están en los datos (`names_mismatch`).
- **Confianza baja en la búsqueda:** el texto del LLM se muestra con el aviso "No estoy seguro…".
- Detalle en `ml/evals/REPORT.md`, sección 1c.

## Alternativas descartadas

- **Todo por RAG, incluidos los cálculos:** un modelo de 4B se equivoca con los números (ADR-002) y las listas salen incompletas.
- **Text-to-SQL:** riesgo de fuga entre pymes y de cifras incorrectas (ADR-002, ADR-005).
- **Agente con herramientas (nivel 3) por defecto:** `qwen3:4b` eligió bien la herramienta en 1 de 4 casos. `qwen3:8b` acierta, pero necesita GPU o un proveedor externo (ADR-003).
