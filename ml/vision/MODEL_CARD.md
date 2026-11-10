# Model card — detector de productos (F2)

> **MODELO DE PRUEBA.** Entrenado con fotos de comida de internet (Snacks), no con productos de una pyme.
> Valida que el pipeline funciona de punta a punta. **Sus métricas no representan el caso real** (AGENTS.md §10).

## Modelo
- RF-DETR Nano (Apache-2.0), `rfdetr` 1.12.0, ajustado 30 épocas, semilla 42, exportado a ONNX (entrada 384×384).
- Versión: `snacks-v1-nano-1`. sha256 del ONNX: `91a3d3a9c41e…` (completo en `models.lock.yaml`).
- Entrenado en Colab (T4). No se guardó el log de entrenamiento, por eso **no hay mAP50 ni mAP50:95** en este card.

## Datos
- Snacks (Open Images), clases `cookie`, `muffin`, `doughnut`, `pretzel`. Fotos CC BY 2.0, cajas CC BY 4.0 (`THIRD_PARTY_NOTICES.md`).
- `snacks-v1` (`dataset_sha256` 13d2f7be…): 816 train / 174 valid / 174 test, repartidos por autor de la foto (sin fuga).
- Son fotos sueltas con pocos objetos, no bandejas con decenas de productos.

## Resultados en test (174 fotos) — `ml/vision/eval_onnx.py`, mismo código que la API
Solo cuentan las fotos donde la clase aparece en la verdad o en la predicción (las demás no informan sobre esa clase).

| Umbral | Fotos×clase | Conteo exacto | Error abs. medio |
|--------|-------------|---------------|------------------|
| 0.3 | 187 | 39.6 % | 0.78 |
| **0.5** (el de la API) | 183 | **50.3 %** | **0.67** |
| 0.7 | 179 | 46.4 % | 0.76 |

Por clase a 0.5: cookie 50 % exacto (error 0.98), muffin 54 % (0.50), doughnut 50 % (0.60), pretzel 45 % (0.69).
La línea base es floja: en la mitad de las fotos el conteo no es exacto, y por eso el flujo exige que la usuaria corrija.
**El umbral objetivo de precisión se fija con fotos reales de la pyme**, después de medir su línea base.

## Latencia (CPU i5-8250U, 8 hilos, sin GPU) — `POST /vision/count` con el servidor real
| Caso | p50 | p95 |
|------|-----|-----|
| Fotos pequeñas del test (n=25) | 401 ms | 440 ms |
| Foto 12 MP sintética (n=15) | 557 ms | 629 ms |
| Primera llamada tras iniciar (modelo ya cargado al arrancar) | 640 ms | — |
| Primera llamada, con carga perezosa (versión anterior) | 1 836 ms | — |

Límites: la foto de 12 MP es una imagen ampliada (0.5 MB), mucho más liviana de decodificar que un JPEG real de
celular (3 a 5 MB); repetir con fotos reales. El benchmark
anterior (169 ms) medía solo la inferencia con una imagen aleatoria; este valor incluye decodificar, preprocesar y postprocesar.

## Segundo modelo de prueba: `synth-recetas-nano-1` (bandejas sintéticas)

> **Datos SINTÉTICOS.** Bandejas dibujadas por `synth.py`, no fotos. Sirve para que "Contar con foto" cuente las
> fotos de `ml/vision/fotos-prueba/` y se una con las recetas de demo. **Sus métricas no representan el caso real.**

- RF-DETR Nano, `rfdetr` 1.12.0, 40 épocas, batch 2, semilla 42, ONNX de entrada 384×384. sha256 `69ad76d8…`
  (completo en `models.lock.yaml`).
- Clases: `empanada_pino`, `canape_salmon`, `brocheta_pollo` (las `vision_class` de las recetas de demo).
- Dataset `synth-recetas-v1` (`dataset_sha256` ed1a125c…): 60 sesiones × 6 bandejas, 2 copias aumentadas;
  756 train / 54 valid / 54 test, repartidos por sesión (sin fuga).
- Entrenado el 10-nov-2026 con `bash ml/vision/train_gpu.sh` (`BATCH=2`) en una NVIDIA RTX 2050 de 4 GB, torch
  2.15.0 + CUDA 13.2, Python 3.14, en unos 57 minutos.

| Medición | Resultado |
|----------|-----------|
| Validación (última época, EMA): mAP50 / mAP50:95 | 0.999 / 0.982 |
| Test (54 bandejas), umbral 0.5, conteo exacto por clase | empanada 100 %, canapé 100 %, brocheta 98 % (error medio 0.02) |
| `fotos-prueba` (12 fotos, `count_test_photos.py`) | 11/12 con conteo exacto; error abs. medio 0.08 por foto. Falla `07_mixta_oscura.jpg` (4 canapés en vez de 3) |
| Latencia en test (`eval_onnx.py`, CPU del mismo equipo) | p50 225 ms, p95 305 ms |

Las cifras casi perfectas se explican porque train y test salen del mismo generador: **no son una estimación de
cómo contará fotos reales.** No hay mAP en test ni matriz de confusión de este modelo (`evaluate.py` no se corrió).

## Límites y uso previsto
- Para validar el pipeline y la interfaz. No usar sus conteos como producto.
- Recomendación de foto (para el modelo real): desde arriba, productos separados y sin apilar, fondo liso.
- Pendiente: entrenar con fotos reales, curva de aprendizaje, matriz de confusión, mAP por clase, repetir latencia en el VPS.
