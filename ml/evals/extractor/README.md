# Evaluación del extractor de pedidos (F3)

`cases.jsonl` tiene 22 pedidos **sintéticos** escritos por el equipo en español de Chile: cantidades en palabras, "media docena", errores de tipeo, emojis, listas con guiones, productos que no existen, un pedido ambiguo y un intento de *prompt injection*. No son pedidos reales; los reales (anonimizados) se agregan en T10.

Cada caso: `{"id", "text", "guests", "date", "items": [[receta esperada | null, cantidad, unidad]]}`. Una receta esperada `null` significa que el producto **no** debe asociarse solo (no existe o es ambiguo). La fecha de referencia es fija: lunes 9-nov-2026.

Campos que se puntúan por caso: invitados, fecha resuelta, y por cada producto: receta, cantidad y unidad; además, que no aparezcan productos inventados.

```bash
docker compose -f infra/docker-compose.yml exec -T api \
  python -m app.modules.quotes.evaluation < ml/evals/extractor/cases.jsonl > ml/evals/extractor/results.json
```

El resumen queda en `results.json` (`summary`) y en el informe de T05/T10. La latencia depende del equipo: anotar dónde se corrió.
