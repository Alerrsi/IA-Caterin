# Fotos de prueba para "Contar con foto" (F2)

**No son fotos reales.** Son bandejas dibujadas por `ml/vision/synth.py` (empanadas, canapés y brochetas con luz de
cocina). Sirven para probar el flujo de la app y comparar el conteo con el valor correcto. Las métricas que salgan de
aquí **no** representan el caso real (AGENTS.md, F2 y §10). Para regenerarlas: `python make_test_photos.py` desde
`ml/vision` (necesita Pillow).

`conteos.csv` tiene el conteo correcto de cada foto (separado por `;`, se abre en Excel):

| Foto | Empanadas | Canapés | Brochetas | Qué prueba |
|------|----------:|--------:|----------:|------------|
| 01_empanadas_pocas.jpg | 8 | 0 | 0 | Un solo producto, grande |
| 02_empanadas_muchas.jpg | 13 | 0 | 0 | Un solo producto, muchos y chicos |
| 03_canapes.jpg | 0 | 13 | 0 | Solo canapés |
| 04_brochetas.jpg | 0 | 0 | 7 | Solo brochetas |
| 05_mixta.jpg | 3 | 3 | 4 | Los tres productos |
| 06_mixta_luz_calida.jpg | 6 | 6 | 2 | Luz cálida de cocina |
| 07_mixta_oscura.jpg | 3 | 3 | 2 | Poca luz |
| 08_mixta_luz_fria.jpg | 3 | 2 | 3 | Luz fría y brillante |
| 09_empanadas_canapes.jpg | 8 | 3 | 0 | Dos productos |
| 10_canapes_brochetas.jpg | 0 | 8 | 5 | Dos productos |
| 11_mixta_chica.jpg | 6 | 5 | 2 | Bandeja lejos (productos chicos) |
| 12_mixta_grande.jpg | 5 | 3 | 1 | Bandeja cerca (productos grandes) |

## Cómo probar en la app

1. Entrar como `duena.llaima@demo.local` (o `duena.aromos@demo.local`) → **Contar con foto**.
2. Subir una foto de esta carpeta (en el celular, pasarla primero al teléfono).
3. Comparar el conteo con la tabla, corregirlo si hace falta y confirmar. La corrección queda guardada.

## Estado actual (10-nov-2026)

**Ya hay un modelo de prueba entrenado: `synth-recetas-nano-1`.** Cuenta bien 11 de estas 12 fotos (falla
`07_mixta_oscura.jpg`: 4 canapés en vez de 3); métricas en `ml/vision/MODEL_CARD.md`. El `.onnx` (116 MB) no está en
el repo: hay que pedirlo al equipo o entrenarlo, y luego instalarlo en tu API. Paso a paso en
[../INSTALAR_MODELO.md](../INSTALAR_MODELO.md).

Sin modelo instalado, la API responde 503 `vision_model_unavailable` ("El conteo por foto no está disponible por
ahora. Cuenta a mano.") y la pantalla ofrece contar a mano. Con estas fotos se puede probar ese camino: subir la foto,
ingresar el conteo y confirmar.

Para que cuente solo (lo hace quien tenga GPU; detalle en `ml/vision/README.md`; con 4 GB de memoria de video usa
`BATCH=2`):

```bash
bash ml/vision/train_gpu.sh                                            # entrena y evalúa con estas fotos
bash ml/vision/install_model.sh ml/vision/runs/synth-recetas-nano-1/onnx   # lo instala en la API
```

El modelo se entrena con las clases de las recetas de demo (`empanada_pino`, `canape_salmon`, `brocheta_pollo`), así
el conteo se une con el producto en Aromos y en Llaima. `count_test_photos.py` compara lo que cuenta con
`conteos.csv` usando el mismo detector de la API.
