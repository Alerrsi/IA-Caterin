# T06 — Conteo de productos por foto
- Estado: en curso
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
- [ ] `ml/vision/README.md`: estructura del dataset (formato COCO), cómo agregar fotos, manifiesto con hash y versión.
- [ ] Script de división train/val/test **sin fuga** (fotos de la misma tanda o sesión van al mismo split).
- [ ] Pre-etiquetado con Grounding DINO o Florence-2 → revisión humana (p. ej. con CVAT o Label Studio).
- [ ] Augmentations realistas: brillo y temperatura de color (luz de cocina), rotación y perspectiva (ángulo de celular), desenfoque leve.
- [ ] Notebook o script de fine-tuning reproducible (semilla, versión del dataset) para Colab, Kaggle o local; export a ONNX.
- [ ] Curva de aprendizaje (rendimiento vs. número de imágenes por clase).
- [ ] `ml/vision/MODEL_CARD.md`: datos, métricas por clase (mAP50, mAP50:95, error absoluto medio de conteo, % de fotos con conteo exacto), matriz de confusión, latencia en CPU, límites, licencias.
- [ ] `modules/vision`: carga del ONNX al iniciar, `POST /vision/count` (EXIF eliminado, redimensión, inferencia, umbral, conteo por clase ↔ `recipe.vision_class`), `POST /vision/productions` (confirmación idempotente con la corrección), `GET /vision/model`.
- [ ] El ONNX se registra en `models.lock.yaml` con su sha256.
- [ ] Medición de latencia de punta a punta en el endpoint.

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
(se completa al terminar)
