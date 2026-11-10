#!/usr/bin/env bash
# Instala un modelo de visión (model.onnx + model.json) en la API de Docker Compose y la reinicia.
#
#   bash ml/vision/install_model.sh ml/vision/runs/synth-recetas-nano-1/onnx
#   bash ml/vision/install_model.sh ~/Descargas/onnx      # la carpeta descomprimida del zip
#
# Copia los archivos al volumen de datos de la API (/data/models/vision/) y revisa que VISION_MODEL_PATH en .env
# apunte ahí. La API carga el modelo al primer conteo; si no lo encuentra, responde 503 y se cuenta a mano.
set -euo pipefail

SRC=${1:?"Uso: $0 <carpeta con model.onnx y model.json>"}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml")
TARGET=/data/models/vision

for f in model.onnx model.json; do
  [[ -f "$SRC/$f" ]] || { echo "Falta $SRC/$f"; exit 1; }
done

"${COMPOSE[@]}" exec -T api mkdir -p "$TARGET"
"${COMPOSE[@]}" cp "$SRC/model.onnx" "api:$TARGET/model.onnx"
"${COMPOSE[@]}" cp "$SRC/model.json" "api:$TARGET/model.json"

current=$(grep -E '^VISION_MODEL_PATH=' "$ROOT/.env" 2>/dev/null | cut -d= -f2- || true)
if [[ -n "$current" && "$current" != "$TARGET/model.onnx" ]]; then
  echo "AVISO: .env tiene VISION_MODEL_PATH=$current. Cámbialo a $TARGET/model.onnx (o bórralo: ese es el valor por defecto)."
fi

"${COMPOSE[@]}" restart api
echo "Modelo instalado en $TARGET. Prueba: 'Contar con foto' con ml/vision/fotos-prueba/05_mixta.jpg"
echo "(esperado: 3 empanadas, 3 canapés y 4 brochetas; ver fotos-prueba/conteos.csv)."
