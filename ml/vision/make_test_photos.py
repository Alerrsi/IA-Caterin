"""Genera `fotos-prueba/`: bandejas SINTÉTICAS con su conteo correcto, para probar "Contar con foto" (F2).

**No son fotos reales.** Usa el mismo dibujo que `synth.py` (empanadas, canapés y brochetas sobre bandejas con luz
de cocina). Cada foto queda con su conteo esperado en `conteos.csv`, para comparar con lo que devuelve la app.
Desde ml/vision:

    python make_test_photos.py
"""

import csv
import random
from pathlib import Path

from synth import make_image

OUT = Path(__file__).parent / "fotos-prueba"

# (archivo, descripción, sesión: tamaño relativo, temperatura, brillo, pesos empanada/canapé/brocheta, semilla)
CASES = [
    ("01_empanadas_pocas.jpg", "Solo empanadas, pocas y grandes, luz normal", 0.09, 1.0, 1.0, (1, 0, 0), 11),
    ("02_empanadas_muchas.jpg", "Solo empanadas, muchas y chicas", 0.05, 1.0, 1.0, (1, 0, 0), 12),
    ("03_canapes.jpg", "Solo canapés", 0.07, 1.0, 1.0, (0, 1, 0), 13),
    ("04_brochetas.jpg", "Solo brochetas", 0.07, 1.0, 1.0, (0, 0, 1), 14),
    ("05_mixta.jpg", "Los tres productos, luz normal", 0.07, 1.0, 1.0, (1, 1, 1), 15),
    ("06_mixta_luz_calida.jpg", "Los tres productos, luz cálida de cocina", 0.07, 1.15, 1.0, (1, 1, 1), 16),
    ("07_mixta_oscura.jpg", "Los tres productos, poca luz (de noche)", 0.07, 1.0, 0.72, (1, 1, 1), 17),
    ("08_mixta_luz_fria.jpg", "Los tres productos, luz fría y brillante", 0.07, 0.9, 1.15, (1, 1, 1), 18),
    ("09_empanadas_canapes.jpg", "Empanadas y canapés", 0.06, 1.05, 0.95, (1, 1, 0), 19),
    ("10_canapes_brochetas.jpg", "Canapés y brochetas", 0.06, 0.95, 1.05, (0, 1, 1), 20),
    ("11_mixta_chica.jpg", "Los tres productos, chicos (bandeja lejos)", 0.05, 1.0, 1.0, (1, 1, 1), 21),
    ("12_mixta_grande.jpg", "Los tres productos, grandes (bandeja cerca)", 0.09, 1.0, 1.0, (1, 1, 1), 22),
]
LABELS = {"empanada": "empanadas", "canape": "canapes", "brocheta": "brochetas"}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows = []
    for name, desc, size, warm, bright, (we, wc, wb), seed in CASES:
        session = {"size": size, "warm": warm, "bright": bright, "w_emp": we, "w_can": wc, "w_bro": wb}
        wanted = [k for k, w in zip(LABELS, (we, wc, wb), strict=True) if w]
        while True:  # que cada bandeja traiga todos los productos pedidos y al menos 6 en total
            img, anns = make_image(random.Random(seed), session)
            counts = {v: sum(1 for a in anns if a["class"] == k) for k, v in LABELS.items()}
            if len(anns) >= 6 and all(counts[LABELS[k]] > 0 for k in wanted):
                break
            seed += 1000
        img.save(OUT / name, "JPEG", quality=85)
        rows.append({"archivo": name, **counts, "total": len(anns), "descripcion": desc})
    with (OUT / "conteos.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, ["archivo", "empanadas", "canapes", "brochetas", "total", "descripcion"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(f"{r['archivo']:28} empanadas={r['empanadas']:2} canapés={r['canapes']:2} brochetas={r['brochetas']:2}")


if __name__ == "__main__":
    main()
