"""Mide el enrutador de intenciones contra el set dorado (sin base de datos, sin LLM). T07.

    python eval_router.py [--threshold 0.65] [--margin 0.03] [--sweep]

Reporta acierto por intención, rechazos correctos en preguntas sin intención, qué parte se resolvió por reglas
(costo cero) y por similitud, y los errores uno por uno. `--sweep` muestra cómo cambia el resultado con el umbral.
El umbral y el margen definitivos los calibra T10 con un set reservado.
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from app.modules.assistant.intents import load_catalog  # noqa: E402
from app.modules.assistant.recognizer import recognize  # noqa: E402

GOLDEN = Path(__file__).with_name("golden.yaml")


def evaluate(threshold: float, margin: float) -> dict[str, object]:
    cat = load_catalog()
    cases = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["cases"]
    per: dict[str, list[bool]] = defaultdict(list)
    errors: list[str] = []
    via: Counter[str] = Counter()
    wrong_route = 0  # enrutó, pero a la intención equivocada (peor que no enrutar)
    for c in cases:
        r = recognize(c["q"], cat, threshold, margin)
        ok = r.intent == c["intent"]
        per[c["intent"] or "(sin intención)"].append(ok)
        via[r.via] += 1
        if not ok:
            wrong_route += r.intent is not None
            errors.append(f"  esperaba {c['intent']!s:16} obtuvo {r.intent!s:16} ({r.via}, {r.score}) «{c['q']}»")
    total = len(cases)
    return {
        "total": total,
        "correct": sum(sum(v) for v in per.values()),
        "wrong_route": wrong_route,
        "per": {k: (sum(v), len(v)) for k, v in per.items()},
        "via": dict(via),
        "errors": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.65)
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--sweep", action="store_true")
    a = ap.parse_args()
    res = evaluate(a.threshold, a.margin)
    total = int(res["total"])  # type: ignore[call-overload]
    print(f"umbral {a.threshold}, margen {a.margin}: {res['correct']}/{total} correctos "
          f"({100 * int(res['correct']) / total:.1f} %), enrutados a la intención equivocada: {res['wrong_route']}")  # type: ignore[call-overload]
    for k, (ok, n) in dict(res["per"]).items():  # type: ignore[call-overload]
        print(f"  {k:18} {ok}/{n}")
    print("resuelto por:", res["via"])
    print("\n".join(res["errors"]) or "sin errores")  # type: ignore[arg-type]
    if a.sweep:
        print("\numbral  correctos  mal enrutados")
        for t in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8):
            r = evaluate(t, a.margin)
            print(f"{t:6}  {r['correct']}/{total}      {r['wrong_route']}")


if __name__ == "__main__":
    main()
