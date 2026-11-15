# Design System — Cáterin

Memoria de la skill `interface-design`. Resumen de marca y reglas en `.claude/skills/caterin-brand/SKILL.md`;
decisiones en `docs/adr/ADR-008-identidad-visual.md` (color, logo) y `docs/adr/ADR-010-estetica-plano.md` (plano de
cocina). Los colores salen de `apps/web/scripts/theme.mjs` (no se escriben a mano).

## Direction

**Personality:** Precision & Function con calidez contenida ("cocina profesional ordenada", dibujada como un plano).
**Foundation:** neutral (tono laurel con croma 2: casi blanco, sin crema ni gris azulado).
**Depth:** borders-only con líneas finas (`hairline`) + cambios de superficie. Única sombra: el botón tecla.

Quién: emprendedora de catering, en el celular, entre la cocina y un evento. Qué: cotizar, revisar stock, responder
clientes. Sensación: tranquila, precisa y confiable, como una cocina limpia antes del servicio.
Firma: cifras de comanda en monoespaciada, línea de corte punteada antes del total, papel cuadriculado de la libreta
de recetas y el panel laurel rayado del login.

## Tokens

### Color (roles en `apps/web/src/index.css`)
```
--color-primary: laurel (#2d6956)         acción principal, enlaces, foco
--color-primary-edge: #004434             borde inferior de la tecla
--color-primary-container: #d1e8dd        acceso destacado, selección en la navegación
--color-tertiary: cobre (#924b29)         acento puntual (≤ 10 %), nunca botones
--color-surface-container-low: #f5f3f1    lienzo de la página y cajón
--color-surface: #faf9f7                  columna de contenido en escritorio
--color-surface-container-lowest: #fff    tarjetas, celdas y campos
--color-hairline: #dbddda                 rieles, celdas, divisores, tarjetas
--color-outline: #757875                  borde de campos y línea de corte (3:1)
--color-brand: #1f4d3f                    solo logo, login y theme-color
```

### Spacing
Base: 4 px (escala de Tailwind). Celda y tarjeta: 16–20 px. Entre bloques: 24 px. Cabecera de pantalla: 16 px
abajo en celular, 24 px y línea fina en escritorio.

### Radius
2 px etiquetas y `kbd` · 4 px campos, botones y navegación · 6 px tarjetas, celdas y avisos · 8 px cajón y login.

### Typography (IBM Plex)
Cuerpo: Plex Sans variable, raíz 17 px, mínimo 15 px. `h1`: Plex Serif 500, 29,75 px (38 px escritorio), interletra
−0,02 em, `text-wrap: balance`. Títulos de sección: Serif 20 px. Cifras: Plex Mono 400 con `tabular-nums` (`.num`).
Frase del login: Serif cursiva.

### Motion
`--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` (150 ms, presión y color); `--ease-drawer: cubic-bezier(0.32, 0.72, 0,
1)` (300 ms, cajón). `motion-reduce` quita el desplazamiento.

## Patterns

### Button (`ui.tsx`)
- Alto mínimo 48 px, relleno 20 px horizontal, radio 4 px, 17 px/500.
- `primary`: relleno laurel + `shadow-key` (borde inferior `primary-edge` de 2 px); al presionar baja 1 px y el borde
  pasa a 1 px. `secondary`: blanco, borde `outline`, `shadow-cap`. `tonal` y `ghost` sin sombra.
- `shortcut="C"`: agrega `aria-keyshortcuts` y `<Kbd>` (solo escritorio con mouse).

### Cells (`ui.tsx`, utilidad `cells`)
- Lista en grilla, borde `hairline` de 1 px, radio 6 px, fondo blanco; cada `<li>` dibuja su línea derecha e inferior
  en una capa encima. Accesos del inicio (destacado a todo el ancho), pymes y productos del catálogo.

### Page (`ui.tsx`)
- Escritorio: columna con rieles `hairline` y cabecera con línea inferior y marcas cuadradas de 7 px en los cruces.
- Título serif, bajada opcional (`description`), acciones a la derecha.

### Card
- Borde `hairline`, fondo blanco, radio 6 px, relleno 16/20 px, sin sombra.

### Total como ticket
- Neto e IVA arriba en mono alineados a la derecha, línea `border-dashed border-outline`, total en mono 36 px.

### Input (`inputClass`)
- Alto 48 px, borde 1 px `outline`, radio 4 px; foco: borde y anillo de 1 px `primary`.

### Status chip
- Radio 2 px, alto 32 px, `px-2.5`, 15 px/500, colores del contenedor del estado.

## Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Laurel en vez de maqui | El usuario pidió colores distintos y un aspecto más profesional | 2026-11-15 |
| Estados con croma ≤ 22 | Los avisos no deben gritar más que la acción principal | 2026-11-15 |
| Se mantienen los nombres de rol MD3 | Cambiarlos tocaba todos los componentes sin cambiar lo que se ve | 2026-11-15 |
| Estética "plano de cocina" (inspirada en zed.dev) | Pedido del usuario; principios traducidos al catering, sin su marca (ADR-010) | 2026-11-15 |
| IBM Plex Sans/Serif/Mono en vez de Roboto y Bricolage | Una familia en tres voces; 101,6 KB de fuentes (antes 85,4 con dos familias) | 2026-11-15 |
| Esquinas de 2–8 px | Las de 8 px y las píldoras se veían blandas para una herramienta de trabajo | 2026-11-15 |
| Sin Plex Mono 500 | Presupuesto; las cifras destacan por tamaño, no por peso | 2026-11-15 |
| Atajos solo `C` y `/` | Los que más se repiten en escritorio; nunca dentro de un campo | 2026-11-15 |
