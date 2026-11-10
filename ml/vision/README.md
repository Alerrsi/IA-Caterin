# ml/vision — conteo de productos por foto (F2, T06)

Datos y entrenamiento del detector (RF-DETR Nano → ONNX). La inferencia vive en `apps/api/app/modules/vision`.

## Entorno

```bash
uv venv --python 3.12 ml/vision/.venv
uv pip install --python ml/vision/.venv/bin/python -r ml/vision/requirements.txt
```

El fine-tuning (`torch`, `rfdetr`) se corre en Colab o Kaggle con GPU; en un equipo sin GPU no es práctico.

## Cómo sacar las fotos (afecta mucho el resultado)

- Desde arriba y de frente, con la bandeja completa en el cuadro.
- Productos separados, sin apilar ni tapar unos con otros: el conteo cae mucho cuando se superponen.
- Fondo liso. Varias luces (cocina, ventana, noche) y varios ángulos leves.
- **Una sesión = una tanda de producción.** Todas las fotos de la misma tanda llevan el mismo `session`.
- Punto de partida: unas decenas de fotos por producto, en al menos 8 a 10 sesiones distintas (menos que eso y
  el split no puede separar bien). Se valida con la curva de aprendizaje, no con una cifra supuesta.

## Estructura

```
data/                    # NO se commitea (fotos de personas y negocios reales)
├── raw/
│   ├── images/*.jpg
│   └── annotations.json     # COCO + "session" en cada imagen
└── v1/                      # versión generada, inmutable
    ├── train/ valid/ test/  # imágenes + _annotations.coco.json (layout que espera RF-DETR)
    └── manifest.json        # semilla, conteos por clase y sha256 de cada archivo
```

Cada imagen de `annotations.json` necesita `"session": "<id>"`. Los nombres de categoría son los `vision_class`
de las recetas (por ejemplo `empanada_pino`), porque así se une el conteo con el producto.

## Comandos

```bash
cd ml/vision
.venv/bin/python dataset.py split --version v1 --seed 42   # sesiones completas a un solo split (70/15/15)
.venv/bin/python dataset.py check data/v1                  # fuga, archivos alterados, clases ausentes
.venv/bin/python -m pytest test_dataset.py
```

`dataset.py split --augment N` agrega N copias aumentadas de cada foto de train (`augment.py`: brillo y temperatura
de color de luz de cocina, rotación y perspectiva leves de celular, espejo, desenfoque leve). Las copias heredan
la sesión de su original y nunca van a valid/test; el manifiesto registra `augment_copies`.

`split` nunca sobrescribe una versión: para cambiar los datos se crea `v2`. El `dataset_sha256` del manifiesto
identifica los datos exactos con que se entrenó un modelo y va en el model card.

## Datos de prueba

Mientras no haya fotos de una pyme real se usa Snacks (Open Images, CC BY; cookie, muffin, doughnut, pretzel):

```bash
# bajar de Hugging Face a data/_snacks: train.csv, val.csv, test.csv (snacks-detection) e images.zip, credits.csv (snacks)
.venv/bin/python prepare_snacks.py                         # -> data/raw (1.164 imágenes, 1.964 cajas)
.venv/bin/python dataset.py split --version snacks-v1
```

La "sesión" es el autor de la foto, para que un mismo fotógrafo no quede repartido entre splits. Son fotos de
comida de internet, no bandejas de una cocina: sirven para validar el pipeline, y el model card debe decirlo.
Sus métricas no se presentan como del caso real (AGENTS.md §10). Atribución en `THIRD_PARTY_NOTICES.md`.

También hay un generador **sintético** de bandejas (empanadas, canapés, brochetas dibujados) para probar el
pipeline completo sin descargar nada. No son fotos reales y sus métricas tampoco se presentan como del caso real:

```bash
.venv/bin/python synth.py --out data/raw-synth-v1 --sessions 30 --per-session 5
.venv/bin/python dataset.py split --raw data/raw-synth-v1 --version synth-v1 --augment 2
```

## Pre-etiquetado (cuando haya fotos reales)

`prelabel.py` sugiere cajas con Grounding DINO tiny (Apache 2.0, se descarga de Hugging Face) a partir de un
texto por clase y escribe un COCO para importar en CVAT o Label Studio. **Una persona revisa y corrige todas las
cajas**; nada de esto va a producción. Necesita `torch` y `transformers` (mejor en Colab):

```bash
python prelabel.py --images fotos/tanda-01 --out fotos/tanda-01/prelabel.coco.json \
    --classes empanada canape --prompts "empanada" "canapé . bocadito" --revision <commit de HF>
```

## Entrenar y evaluar

En Colab o Kaggle (GPU), con `ml/vision/` y `data/snacks-v1` subidos:

```bash
pip install "rfdetr[train,onnx]==1.12.0"
python train.py --dataset data/snacks-v1 --version snacks-v1-nano-1 --epochs 30
```

Deja `runs/<version>/onnx/model.onnx` y `model.json` (versión, clases, tamaño de entrada, sha256 del dataset y del
ONNX). Se baja esa carpeta y se evalúa en tu equipo con el **mismo código que usa la API**:

```bash
.venv/bin/python eval_onnx.py --model runs/snacks-v1-nano-1/onnx --dataset data/snacks-v1 --out eval.json
```

Reporta, por clase y por umbral (0.3, 0.5, 0.7), el error absoluto medio de conteo y el % de fotos con conteo
exacto, más la latencia de punta a punta en esa CPU. `evaluate.py` (mismos argumentos) calcula además AP50 y
AP50:95 por clase y la matriz de confusión (IoU ≥ 0.5, con la fila/columna "fondo"), con el mismo detector:

```bash
.venv/bin/python evaluate.py --model runs/snacks-v1-nano-1/onnx --dataset data/snacks-v1 --out runs/snacks-v1-nano-1/eval.json
```

Curva de aprendizaje (varios entrenamientos con N fotos de train y el mismo test; en GPU):

```bash
python learning_curve.py --dataset data/snacks-v1 --sizes 25 50 100 200 --epochs 10 --out runs/curve-snacks-v1
```

Latencia de `POST /vision/count` con la API corriendo y fotos sintéticas de 12 MP (mide latencia, no precisión):

```bash
.venv/bin/python bench_count.py --email duena.aromos@demo.local --password caterin-demo-2026   # -> runs/bench_count.json
```

Para usar el modelo en la API: copiar `model.onnx` y `model.json` a la carpeta de `VISION_MODEL_PATH`
(por defecto `/data/models/vision/`).

## Pendiente

Con fotos reales (T10): pre-etiquetar y revisar, reentrenar con `--augment`, correr `evaluate.py` y
`learning_curve.py`, y completar `MODEL_CARD.md` (mAP, matriz de confusión, umbral objetivo). Los scripts ya
están probados con datos sintéticos y el ONNX diminuto de las pruebas de la API, no con un modelo entrenado.
