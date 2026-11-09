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

`split` nunca sobrescribe una versión: para cambiar los datos se crea `v2`. El `dataset_sha256` del manifiesto
identifica los datos exactos con que se entrenó un modelo y va en el model card.

## Datos de prueba

Si se parte con fotos de prueba (no de una pyme real), el model card debe decirlo y sus métricas no se
presentan como del caso real (AGENTS.md §10).

## Pendiente

Pre-etiquetado, augmentations, fine-tuning, export ONNX, curva de aprendizaje y `MODEL_CARD.md`.
