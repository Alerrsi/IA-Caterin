# ADR-002 — Los números los calcula el código, no el LLM

- Estado: aceptado (9-nov-2026)
- Contexto en: `AGENTS.md` principios 4 y 5, sección 4

## Contexto

Una cotización mal calculada le cuesta plata directa a la emprendedora: si cobra de menos pierde margen, y si compra de menos le falta producto el día del evento. Los LLM:

- Fallan en aritmética de varios pasos, sobre todo los modelos pequeños que se pueden correr en CPU (`qwen3:4b`).
- No son reproducibles: con la misma entrada pueden dar cifras distintas.
- No dejan un rastro auditable de cómo llegaron a un número.

Además, el benchmark propio mostró que `qwen3:4b` sacó 7 de 8 campos en la extracción de pedidos (`bench_results.json`). Incluso en una tarea más simple que calcular, se equivoca a veces.

## Decisión

1. **Todo número de negocio** (cantidades de insumos, merma, stock descontado, presentaciones a comprar, precios, costos, márgenes, IVA y totales) se calcula en **funciones puras de Python** con `Decimal`.
2. El LLM solo hace dos cosas:
   - **Extraer y normalizar** texto a una estructura validada con Pydantic (pedido → productos y cantidades), que la usuaria **confirma** en una tabla editable antes de calcular.
   - **Redactar** una respuesta a partir de datos ya calculados.
3. **Verificación de cifras en la redacción:** toda cifra que aparezca en el texto del LLM tiene que estar en el dato de entrada (comparando números normalizados: `21.000`, `21000` y `$21.000` cuentan como el mismo). Si aparece una que no está, se descarta la redacción y se entrega la plantilla de nivel 0.
4. **Dinero:** CLP sin decimales, `numeric(12,0)` en la base de datos y `Decimal` cuantizado a 1 en Python, con `ROUND_HALF_UP` por línea y en los totales. **Nunca `float`.**
5. **Cantidades:** `numeric(14,3)` en unidad base (g, ml, unidad). Las conversiones están en una tabla fija en el código; masa ↔ volumen solo con una densidad explícita.
6. **Trazabilidad:** cada cotización guarda el snapshot de precios, los supuestos y la versión del motor de cálculo (`calc_version`), y se puede reproducir.

## Alternativas consideradas

- **Que el LLM calcule y el código verifique:** duplica el trabajo y, si no coinciden, igual gana el código.
- **Que el LLM llame a una calculadora (tool calling):** `qwen3:4b` acertó 1 de 4 casos de tool calling en el benchmark; no es confiable con este hardware (ADR-005).
- **Text-to-SQL:** riesgo de consultas incorrectas, fuga entre pymes y SQL inseguro. Descartado.

## Consecuencias

- El motor de cálculo se testea a fondo con casos reales de catering (conversión de unidades, mermas, redondeos, proveedor sin stock) en T05.
- La experiencia de "IA" en F3 está en ahorrar el tipeo del pedido, no en "adivinar" el precio. Hay que comunicarlo bien en la demo.
- Cualquier cambio en las reglas de redondeo o de IVA cambia `calc_version` y se documenta.
