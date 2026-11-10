# Instalar el modelo de visión ("Contar con foto")

Guía para que la página cuente productos en una foto. Sin modelo, la API responde 503
`vision_model_unavailable` y la pantalla pide contar a mano.

> El modelo actual es **de prueba**: `synth-recetas-nano-1`, entrenado con bandejas **sintéticas** (dibujadas por
> `synth.py`). Cuenta bien las fotos de `fotos-prueba/` (11 de 12), pero **no sirve para fotos reales**. Métricas en
> [MODEL_CARD.md](MODEL_CARD.md).

## 1. Conseguir el modelo

El archivo `model.onnx` pesa 116 MB y **no está en el repo**: GitHub no acepta archivos de más de 100 MB y
AGENTS.md pide no commitear pesos. Tienes dos opciones:

- **Pedirlo al equipo:** el zip `modelo-synth-recetas-nano-1.zip` (100 MB), por Drive o por release de GitHub.
- **Entrenarlo tú**, si tienes GPU NVIDIA: ver la [sección 5](#5-entrenarlo-tú-mismo).

Descomprime el zip en una carpeta, por ejemplo `~/Descargas/modelo-vision/`. Los archivos vienen sueltos, sin
subcarpeta:

```
modelo-vision/
├── model.onnx         el detector (116 MB)
├── model.json         versión, clases y tamaño de entrada; la API lo necesita junto al .onnx
├── eval_test.json     métricas del test sintético (no lo usa la API)
└── fotos_prueba.json  conteo de las 12 fotos de prueba (no lo usa la API)
```

Si lo entrenaste tú, la carpeta equivalente es `ml/vision/runs/synth-recetas-nano-1/onnx/`.

## 2. Revisar que el archivo llegó completo

El sha256 debe ser el que está en `models.lock.yaml` (`69ad76d854daccce273173b254557c13e39291b4335ca69acfa84bae97b4828f`):

```bash
sha256sum ~/Descargas/modelo-vision/model.onnx
```

En Windows (PowerShell): `Get-FileHash $HOME\Downloads\modelo-vision\model.onnx`. Si no coincide, el archivo se
descargó mal o es otra versión: vuelve a pedirlo.

## 3. Instalarlo en la API

Con Docker Compose levantado (`docker compose -f infra/docker-compose.yml up -d`), desde la raíz del repo:

```bash
bash ml/vision/install_model.sh ~/Descargas/modelo-vision
```

El script copia `model.onnx` y `model.json` a `/data/models/vision/` dentro del contenedor `api` y reinicia la API.
El reinicio es necesario: la API busca el modelo una sola vez, al arrancar.

**Sin bash (Windows, PowerShell)**, los mismos pasos a mano desde la raíz del repo:

```powershell
docker compose -f infra/docker-compose.yml exec -T api mkdir -p /data/models/vision
docker compose -f infra/docker-compose.yml cp $HOME\Downloads\modelo-vision\model.onnx api:/data/models/vision/model.onnx
docker compose -f infra/docker-compose.yml cp $HOME\Downloads\modelo-vision\model.json api:/data/models/vision/model.json
docker compose -f infra/docker-compose.yml restart api
```

Si en tu `.env` cambiaste `VISION_MODEL_PATH`, déjalo en `/data/models/vision/model.onnx` (el valor por defecto) o
bórralo.

## 4. Probar que cuenta

1. Abre http://localhost:5173 y entra como `duena.aromos@demo.local` o `duena.llaima@demo.local`
   (contraseña de demo: `caterin-demo-2026`).
2. Ve a **Contar con foto** y sube `ml/vision/fotos-prueba/05_mixta.jpg`.
3. Debería contar **3 empanadas, 3 canapés y 4 brochetas**. Compara las demás fotos con
   [fotos-prueba/conteos.csv](fotos-prueba/conteos.csv). `07_mixta_oscura.jpg` cuenta un canapé de más: es un error
   conocido del modelo de prueba.

Desde la terminal (Linux/macOS), lo mismo contra la API:

```bash
API=http://localhost:8000/api/v1
TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"duena.aromos@demo.local","password":"caterin-demo-2026"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X POST $API/vision/count -H "Authorization: Bearer $TOKEN" \
  -F "image=@ml/vision/fotos-prueba/05_mixta.jpg" | python3 -m json.tool | head -25
```

La respuesta trae `"model_version": "synth-recetas-nano-1"` y un conteo por receta.

### Si no funciona

| Qué pasa | Por qué | Qué hacer |
|----------|---------|-----------|
| Sigue diciendo "Cuenta a mano" (503) | La API no encontró `model.onnx` y `model.json` juntos, o no se reinició después de copiarlos | Revisa `docker compose -f infra/docker-compose.yml exec api ls -la /data/models/vision` y reinicia la API |
| En los logs sale "modelo de visión no encontrado" | Igual que arriba, o `VISION_MODEL_PATH` apunta a otro lado | `docker compose -f infra/docker-compose.yml logs api \| grep -i visión` y revisa el `.env` |
| Cuenta, pero no lo une con ninguna receta | La pyme no tiene recetas con esas `vision_class` (`empanada_pino`, `canape_salmon`, `brocheta_pollo`) | Usa una pyme de demo (Aromos o Llaima) |
| El modelo desapareció | Se borró el volumen `apidata` (por ejemplo con `docker compose down -v`) | Vuelve a correr el paso 3. Reiniciar o reconstruir la API **no** lo borra |

## 5. Entrenarlo tú mismo

Con una GPU NVIDIA (probado en una RTX 2050 de 4 GB; tardó unos 57 minutos), desde la raíz del repo:

```bash
BATCH=2 bash ml/vision/train_gpu.sh     # con 8 GB o más de memoria de video puedes quitar BATCH=2
bash ml/vision/install_model.sh ml/vision/runs/synth-recetas-nano-1/onnx
```

`train_gpu.sh` crea el entorno `.venv-gpu`, genera las bandejas sintéticas, entrena, exporta a ONNX, cuenta las
fotos de prueba y deja el zip para compartir en `ml/vision/runs/synth-recetas-nano-1/`. Sin GPU se puede usar
[colab_train.ipynb](colab_train.ipynb). Más detalles en [README.md](README.md).

Con la misma semilla el resultado debería ser muy parecido, pero el sha256 del `.onnx` puede cambiar según la GPU y
la versión de torch. Si es distinto al de `models.lock.yaml`, comprueba las métricas con
`count_test_photos.py` antes de compartirlo.
