#!/usr/bin/env bash
# Entrena el detector de PRUEBA (datos sintéticos) en un equipo con GPU NVIDIA y deja el modelo listo para la API.
#
#   bash ml/vision/train_gpu.sh                 # todo: entorno, datos, entrenamiento, evaluación y paquete
#   EPOCHS=10 bash ml/vision/train_gpu.sh       # menos épocas (más rápido, peor modelo)
#   SKIP_INSTALL=1 bash ml/vision/train_gpu.sh  # reusar el entorno ya instalado
#
# También sirve en Colab/Kaggle (GPU T4): clonar el repo y correr `!bash ml/vision/train_gpu.sh`.
# Al terminar deja `ml/vision/runs/$MODEL/modelo-$MODEL.zip` con model.onnx + model.json. Para usarlo en la API:
#   bash ml/vision/install_model.sh ml/vision/runs/$MODEL/onnx
#
# Los datos son SINTÉTICOS (bandejas dibujadas por synth.py): el modelo sirve para probar la función de punta a
# punta, NO para fotos reales. Sus métricas se reportan como sintéticas (AGENTS.md, F2 y §10).
set -euo pipefail

cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
VENV=${VENV:-.venv-gpu}
DATA=${DATA:-synth-recetas-v1}        # versión del dataset (dataset.py no sobrescribe una versión existente)
MODEL=${MODEL:-synth-recetas-nano-1}  # versión del modelo (va en model.json y en la API)
EPOCHS=${EPOCHS:-40}
BATCH=${BATCH:-8}
SESSIONS=${SESSIONS:-60}
PER_SESSION=${PER_SESSION:-6}
AUGMENT=${AUGMENT:-2}

step() { printf '\n==> %s\n' "$*"; }

step "GPU"
if command -v nvidia-smi >/dev/null; then
  nvidia-smi -L
else
  echo "AVISO: no veo nvidia-smi. Sin GPU el entrenamiento no es práctico (en CPU no terminó, ver runs/smoke.log)."
  [[ "${ALLOW_CPU:-0}" == "1" ]] || { echo "Para intentarlo igual: ALLOW_CPU=1"; exit 1; }
fi

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  step "Entorno ($VENV)"
  [[ -d "$VENV" ]] || "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  # rfdetr trae torch; si tu CUDA necesita otra build de torch, instálala antes con el índice de pytorch.org.
  "$VENV/bin/pip" install -q -r requirements.txt "rfdetr[train,onnx]==1.12.0"
fi
PY="$VENV/bin/python"
"$PY" -c "import torch; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available())"

step "Datos sintéticos con las clases de las recetas (empanada_pino, canape_salmon, brocheta_pollo)"
if [[ -d "data/$DATA" ]]; then
  echo "data/$DATA ya existe: se reutiliza (para regenerar, usa otro DATA=...)."
else
  "$PY" synth.py --out "data/raw-$DATA" --sessions "$SESSIONS" --per-session "$PER_SESSION" --recipe-classes
  "$PY" dataset.py split --raw "data/raw-$DATA" --version "$DATA" --augment "$AUGMENT"
fi
"$PY" dataset.py check "data/$DATA"

step "Entrenamiento ($EPOCHS épocas) y export a ONNX"
"$PY" train.py --dataset "data/$DATA" --version "$MODEL" --epochs "$EPOCHS" --batch-size "$BATCH"

step "Evaluación (mismo detector que la API)"
"$PY" eval_onnx.py --model "runs/$MODEL/onnx" --dataset "data/$DATA" --split test --out "runs/$MODEL/eval_test.json"
"$PY" count_test_photos.py --model "runs/$MODEL/onnx" --out "runs/$MODEL/fotos_prueba.json"

step "Paquete"
(cd "runs/$MODEL" && rm -f "modelo-$MODEL.zip" && "$PY" -m zipfile -c "modelo-$MODEL.zip" onnx/model.onnx onnx/model.json eval_test.json fotos_prueba.json)
echo "Listo: ml/vision/runs/$MODEL/modelo-$MODEL.zip"
echo "Instalar en la API:  bash ml/vision/install_model.sh ml/vision/runs/$MODEL/onnx"
echo "No subas el .onnx al repo (pesa decenas de MB): compártelo por Drive o como release de GitHub."
