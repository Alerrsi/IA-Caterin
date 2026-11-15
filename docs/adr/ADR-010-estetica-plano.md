# ADR-010 — Estética "plano de cocina" (inspirada en zed.dev)

- Estado: **aceptado** (15-nov-2026: el usuario aceptó todas las recomendaciones del plan). Implementado en la rama
  `feat/T16-estetica-plano`; se integra a `main` cuando el usuario revise las capturas.
- Contexto en: ADR-008 (identidad visual), T16 (plan detallado).

## Contexto

El usuario pidió integrar detalles o la estética de https://zed.dev/ en otra rama, primero como plan. Zed es un editor
de código; su sitio se reconoce por líneas finas tipo plano, tipografía en tres voces (serif, cuerpo de máquina de
escribir y monoespaciada), esquinas de 2–4 px, botones con borde de tecla y un solo color de acento.

## Decisión

1. Se toman los **principios**, no la marca: nada de su logo, nombre, textos, azul, fuentes propias ni diagramaciones
   exactas.
2. Se traducen al catering: papel cuadriculado de la libreta de recetas, cifras de comanda en monoespaciada, línea de
   corte punteada del ticket, rayado en el panel del login (T16, sección 2).
3. Tipografía IBM Plex (Serif para títulos, Sans para el cuerpo, Mono para cifras), OFL y autoalojada; se retiran
   Roboto y Bricolage Grotesque. Medido: 151,9 KB de fuentes y marca (presupuesto 200 KB; antes 168,6 KB).
4. Esquinas de 2–8 px, líneas finas como estructura y una sola sombra (la del botón tecla).
5. Se mantienen la paleta laurel/cobre, AA, 48 px de área táctil, textos de 15 px como mínimo (salvo las etiquetas ya existentes de la barra inferior) y el funcionamiento sin
   red.
6. Skills nuevas: `web-interface-guidelines` (Vercel, MIT, copia fija) para los detalles de interfaz y
   `emil-design-eng` (Emil Kowalski, MIT) para el movimiento y la sensación al presionar. Origen en
   `.claude/skills/SOURCES.md`.

## Alternativas descartadas

- **Copiar la estética tal cual** (azul, texto de 12 px, cuerpo en monoespaciada): no cumple AA ni sirve a una usuaria
  no técnica en el celular, y se parecería demasiado a otra marca.
- **No cambiar nada:** la identidad de T14 ya es correcta; esto es un pulido opcional que el usuario pidió.

## Consecuencias

- Cambian fuentes, tokens de forma y algunos componentes; la estructura de `ui.tsx` y de las pantallas se mantiene.
- El logotipo se regenera en IBM Plex Serif.
- Riesgo de que se vea "de programadores": se mitiga con la traducción al mundo de la cocina y se revisa con capturas
  antes de integrar.

## Resultado

Detalle de lo hecho, la verificación y las diferencias con el plan en `docs/tasks/T16-estetica-plano.md` (sección 10).
