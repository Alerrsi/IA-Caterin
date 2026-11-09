# Hoja de verificación — costo de "Empanadas de pino" (seed de demo)

Cálculo hecho a mano (9-nov-2026) con los datos **sintéticos** de `app/db/seed.py`, para comparar con
`GET /api/v1/recipes/{id}/cost` (prueba `test_seed_recipe_cost_matches_hand_calculation`).

- Rendimiento de la receta: 12 unidades. Se calcula el costo de 12 unidades.
- Merma por defecto de la pyme: 5 %. Cebolla tiene merma propia de 10 %.
- Todos los precios del seed incluyen IVA. Se elige la presentación más barata por unidad base.
- Necesario = cantidad × (1 + merma). Costo de la línea = necesario × precio por unidad base, redondeado a pesos (mitad hacia arriba).

| Insumo | Cantidad | Merma | Necesario | Mejor precio | $/unidad base | Cálculo | Costo |
|--------|----------|-------|-----------|--------------|---------------|---------|-------|
| Harina sin polvos | 600 g | 5 % | 630 g | Harinas Cautín, saco 25 kg $21.000 | 0,84 | 630 × 0,84 = 529,2 | 529 |
| Manteca | 120 g | 5 % | 126 g | Harinas Cautín, 1 kg $2.990 | 2,99 | 126 × 2,99 = 376,74 | 377 |
| Carne molida | 700 g | 5 % | 735 g | Ñielol, 1 kg $7.990 | 7,99 | 735 × 7,99 = 5.872,65 | 5.873 |
| Cebolla | 700 g | 10 % | 770 g | El Huerto, 1 kg $990 | 0,99 | 770 × 0,99 = 762,3 | 762 |
| Huevo | 3 u | 5 % | 3,15 u | Ñielol, 30 u $6.490 | 216,333… | 3,15 × 6.490 / 30 = 681,45 | 681 |
| Aceituna negra | 12 u | 5 % | 12,6 u | El Huerto, 100 u $3.490 | 34,9 | 12,6 × 34,9 = 439,74 | 440 |
| Pasas | 40 g | 5 % | 42 g | El Huerto, 500 g $2.490 | 4,98 | 42 × 4,98 = 209,16 | 209 |
| Comino | 3 g | 5 % | 3,15 g | El Huerto, 100 g $990 | 9,9 | 3,15 × 9,9 = 31,185 | 31 |
| Ají de color | 5 g | 5 % | 5,25 g | El Huerto, 100 g $990 | 9,9 | 5,25 × 9,9 = 51,975 | 52 |
| Sal | 10 g | 5 % | 10,5 g | Harinas Cautín, 1 kg $590 | 0,59 | 10,5 × 0,59 = 6,195 | 6 |
| **Total** | | | | | | | **8.960** |

Costo por unidad: 8.960 / 12 = 746,67 → **$747**.
