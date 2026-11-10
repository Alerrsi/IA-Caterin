"""Calibración del umbral y el margen del enrutador con el set RESERVADO (T10). Sin base de datos ni LLM.

    python calibrate_router.py [--set heldout.yaml] [--out calibration.json]

Para cada combinación de umbral (0.40 a 0.90) y margen reporta:
- acierto: casos con la intención esperada (incluye no enrutar cuando se esperaba `null`);
- cobertura: casos que se enrutaron a alguna intención;
- erróneo: casos enrutados a una intención distinta de la esperada (peor que no enrutar: responde otra cosa).
Propone el punto con mayor acierto sujeto a erróneo ≤ 5 % (AGENTS.md / ADR-005). Las reglas (keywords) no
dependen del umbral: el barrido solo mueve lo que se resuelve por similitud.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from app.modules.assistant.intents import load_catalog  # noqa: E402
from app.modules.assistant.recognizer import recognize  # noqa: E402

HERE = Path(__file__).parent
THRESHOLDS = [round(0.40 + 0.05 * i, 2) for i in range(11)]
MARGINS = [0.0, 0.03, 0.05, 0.10]
MAX_WRONG = 0.05


def run(cases: list[dict[str, Any]], threshold: float, margin: float) -> dict[str, Any]:
    cat = load_catalog()
    ok = routed = wrong = 0
    errors = []
    via: dict[str, int] = {}
    for c in cases:
        r = recognize(c["q"], cat, threshold, margin)
        via[r.via] = via.get(r.via, 0) + 1
        routed += r.intent is not None
        if r.intent == c["intent"]:
            ok += 1
            continue
        wrong += r.intent is not None and r.intent != c["intent"]
        errors.append({"q": c["q"], "expected": c["intent"], "got": r.intent, "via": r.via, "score": r.score})
    n = len(cases)
    return {
        "threshold": threshold,
        "margin": margin,
        "n": n,
        "accuracy": round(ok / n, 4),
        "coverage": round(routed / n, 4),
        "wrong_rate": round(wrong / n, 4),
        "correct": ok,
        "wrong": wrong,
        "via": via,
        "errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, default=HERE / "heldout.yaml")
    ap.add_argument("--out", type=Path, default=HERE / "calibration.json")
    a = ap.parse_args()
    cases = yaml.safe_load(a.set.read_text(encoding="utf-8"))["cases"]

    current = run(cases, 0.65, 0.03)
    grid = [run(cases, t, m) for t in THRESHOLDS for m in MARGINS]
    eligible = [g for g in grid if g["wrong_rate"] <= MAX_WRONG]
    # Mayor acierto; a igual acierto, menos erróneo y umbral más alto (más conservador).
    best = max(eligible, key=lambda g: (g["accuracy"], -g["wrong_rate"], g["threshold"])) if eligible else None

    print(f"Set: {a.set.name} ({len(cases)} casos)")
    print(f"ACTUAL 0.65/0.03: acierto {current['accuracy']:.1%}, cobertura {current['coverage']:.1%}, "
          f"erróneo {current['wrong_rate']:.1%} ({current['wrong']}), resuelto por {current['via']}")
    print("\numbral margen  acierto  cobertura  erróneo")
    for g in grid:
        mark = " <- propuesto" if best is g else ""
        print(f"{g['threshold']:6} {g['margin']:6}  {g['accuracy']:7.1%}  {g['coverage']:9.1%}  {g['wrong_rate']:7.1%}{mark}")
    if best:
        print(f"\nPropuesto: umbral {best['threshold']}, margen {best['margin']} "
              f"(acierto {best['accuracy']:.1%}, erróneo {best['wrong_rate']:.1%})")
    print("\nErrores con el umbral ACTUAL:")
    for e in current["errors"]:
        print(f"  esperaba {e['expected']!s:18} obtuvo {e['got']!s:18} ({e['via']}, {e['score']}) «{e['q']}»")

    out = {
        "set": a.set.name,
        "n": len(cases),
        "max_wrong_rate": MAX_WRONG,
        "current": current,
        "proposed": {k: best[k] for k in ("threshold", "margin", "accuracy", "coverage", "wrong_rate")} if best else None,
        "grid": [{k: g[k] for k in ("threshold", "margin", "accuracy", "coverage", "wrong_rate")} for g in grid],
    }
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
