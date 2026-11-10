# T06 — Conteo de productos por foto
- Estado: hecha (con datos de prueba; lo que exige fotos reales pasa a T10)
- Depende de: T04
- Funcionalidad: F2

## Objetivo
Que al terminar una tanda de producción la emprendedora saque una foto a la bandeja y Cáterin le diga cuántas empanadas, canapés o brochetas hay, para que solo tenga que corregir si algo está mal en vez de contar a mano.

## Contexto y decisiones previas
- Modelo: RF-DETR Nano → Small si no alcanza (ADR-003). Inferencia con ONNX Runtime en CPU.
- Medido: 169 ms p50 de inferencia pura a 384×384 en i5-8250U, con imagen aleatoria.
- Sin dataset real al inicio: un dataset público (p. ej. Food-101 es de **clasificación**; para detección hay que buscar uno con cajas o pre-etiquetar) solo valida el pipeline. **Sus métricas no se presentan como del caso real.**
- La parte de `ml/vision` (dataset, entrenamiento) puede empezar en paralelo con T01–T04.

## Entregables
- [x] `ml/vision/README.md`: estructura del dataset (formato COCO), cómo agregar fotos, manifiesto con hash y versión. — **hecho**
- [x] Script de división train/val/test **sin fuga** (fotos de la misma tanda o sesión van al mismo split). — **hecho**
- [ ] Pre-etiquetado con Grounding DINO o Florence-2 → revisión humana (p. ej. con CVAT o Label Studio). — **script listo (`prelabel.py`, Grounding DINO tiny); falta usarlo con fotos reales sin etiquetar (T10)**
- [ ] Augmentations realistas: brillo y temperatura de color (luz de cocina), rotación y perspectiva (ángulo de celular), desenfoque leve. — **hecho como opción `dataset.py split --augment N` (`augment.py`, solo train, hereda la sesión); probado con datos sintéticos. `snacks-v1-nano-1` se entrenó sin ellas; reentrenar con fotos reales (T10)**
- [x] Notebook o script de fine-tuning reproducible (semilla, versión del dataset) para Colab, Kaggle o local; export a ONNX. — **hecho (`train.py` + `colab_train.ipynb`, semilla y versión del dataset; el export a ONNX corrió en Colab)**
- [ ] Curva de aprendizaje (rendimiento vs. número de imágenes por clase). — **script listo (`learning_curve.py`, rehace el manifiesto de cada subconjunto); falta correrlo en GPU con fotos reales (T10)**
- [ ] `ml/vision/MODEL_CARD.md`: datos, métricas por clase (mAP50, mAP50:95, error absoluto medio de conteo, % de fotos con conteo exacto), matriz de confusión, latencia en CPU, límites, licencias. — **parcial: datos, conteo por clase, latencia y límites. `evaluate.py` ya calcula AP50, AP50:95 y la matriz de confusión con el detector de la API; falta correrlo con el modelo entrenado y fijar el umbral objetivo (T10)**
- [x] `modules/vision`: carga del ONNX al iniciar, `POST /vision/count` (EXIF eliminado, redimensión, inferencia, umbral, conteo por clase ↔ `recipe.vision_class`), `POST /vision/productions` (confirmación idempotente con la corrección), `GET /vision/model`. — **hecho (el historial `GET /vision/productions` no estaba en esta lista y queda pendiente hasta que la PWA lo pida)**
- [x] El ONNX se registra en `models.lock.yaml` con su sha256. — **hecho**
- [x] Medición de latencia de punta a punta en el endpoint. — **hecho (con foto de 12 MP sintética; repetir con JPEG real, T10)**

- [ ] **Modelo de prueba entrenado (10-nov-2026, encargado a quien tenga GPU):** `bash ml/vision/train_gpu.sh` genera datos sintéticos con las clases de las recetas de demo, entrena RF-DETR Nano, exporta ONNX + `model.json` y lo evalúa contra `ml/vision/fotos-prueba/conteos.csv`. Después, `bash ml/vision/install_model.sh <carpeta onnx>` lo instala en la API. Hasta entonces `/vision/count` responde 503 y se cuenta a mano. Probado sin GPU: generar los datos, dividirlos, verificarlos y comparar con un detector simulado. El entrenamiento y el export **no se han corrido**.

## Criterios de aceptación
- `POST /vision/count` con una foto de celular de 12 MP devuelve el conteo en p95 ≤ 2 s en el equipo de referencia (**propuesta**, se mide e informa aunque no alcance).
- La corrección de la usuaria queda en `production_record` con el conteo detectado, el confirmado, la versión del modelo y las detecciones.
- El model card distingue con claridad las métricas del dataset público/sintético de las de fotos reales (si las hay).
- El umbral objetivo de precisión se fija en el model card **después** de medir la línea base.

## Pruebas requeridas
- Unitarias: preprocesamiento (tamaños, orientación EXIF antes de eliminarlo), postprocesamiento y conteo, mapeo clase ↔ receta.
- Integración: endpoint con una imagen de prueba y un ONNX pequeño de prueba; aislamiento A/B en producciones.
- Evaluación: split de test con mAP, error de conteo y latencia (T10).

## Fuera de alcance
- Inferencia en el teléfono, estimación de peso o porción, clasificador de segunda etapa (salvo que la matriz de confusión lo justifique).

## Riesgos y preguntas abiertas
- **Sin fotos reales no hay modelo útil.** Conseguir una pyme que preste fotos (pregunta 6 del índice) es el mayor riesgo de F2.
- Productos amontonados o superpuestos (empanadas apiladas) pueden bajar mucho la precisión del conteo; documentar en el model card la forma recomendada de sacar la foto.
- Verificar la licencia de los pesos de RF-DETR y de los datasets usados.

## Resumen de cierre
**Qué se hizo.** Módulo `modules/vision` (`/vision/count`, `/vision/productions` idempotente, `/vision/model`) con carga del ONNX al iniciar y 503 claro si falta el modelo. Pipeline de datos en `ml/vision` (split sin fuga por sesión, manifiesto con hash, verificación). Entrenamiento y export en Colab (`train.py`, `colab_train.ipynb`) y evaluación con el mismo código de producción (`eval_onnx.py`). Modelo de **prueba** `snacks-v1-nano-1` (Snacks, CC BY) registrado en `models.lock.yaml`. Se verificó en el código de `rfdetr` 1.12.0 y con el modelo entrenado que el ONNX trae `dets` y `labels` con una ranura extra sin entrenar, que el postprocesamiento descarta. 15 pruebas de visión, incluido el `OnnxDetector` real; corre también en el contenedor de la API.

**Medido (modelo de prueba, CPU i5-8250U).** Conteo exacto 50,3 % y error medio 0,67 en test a umbral 0,5. `POST /vision/count`: p50 401 ms con fotos pequeñas y 557 ms (p95 629 ms) con una foto sintética de 12 MP; meta p95 ≤ 2 s cumplida con esa salvedad.

**Qué quedó pendiente (traspasado a T10, depende de la pregunta 6 del índice).** Fotos reales de una pyme: reentrenar, mAP por clase, matriz de confusión, curva de aprendizaje, umbral objetivo de precisión y latencia con JPEG de celular y en el VPS. También pre-etiquetado y augmentations propias, e historial `GET /vision/productions`.

**Riesgos.** Las cifras de precisión son de fotos de internet con pocos objetos y **no predicen** el desempeño sobre bandejas reales; con apilado o superposición pueden ser peores. Hasta tener fotos reales el criterio de precisión de F2 no está demostrado. Para usar el modelo en Docker hay que copiar `model.onnx` y `model.json` al volumen en `/data/models/vision/` (los pesos no se commitean).

**Actualización (9-nov-2026).** Se integraron scripts que estaban fuera del repo, adaptados al detector y al
`train.py` actuales: `augment.py` (opción `--augment` de `dataset.py split`), `evaluate.py` (mAP y matriz de
confusión), `learning_curve.py`, `prelabel.py`, `synth.py` (dataset sintético de bandejas, solo para probar el
pipeline) y `bench_count.py`. Probados de punta a punta con datos sintéticos y el ONNX diminuto de las pruebas:
las cifras de esa prueba no significan nada y no se reportan. Sigue pendiente lo mismo que antes, con fotos reales.
