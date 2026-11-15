# Design System — Cáterin

Memoria de la skill `interface-design`. Resumen de marca y reglas en `.claude/skills/caterin-brand/SKILL.md`;
decisión en `docs/adr/ADR-008-identidad-visual.md`. Los colores salen de `apps/web/scripts/theme.mjs` (no se escriben
a mano).

## Direction

**Personality:** Utility & Function con calidez contenida ("cocina profesional ordenada").
**Foundation:** neutral (tono laurel con croma 2: casi blanco, sin crema ni gris azulado).
**Depth:** borders-only (bordes `outline-variant` + cambios de superficie). Sin sombras salvo `hover` de botones.

Quién: emprendedora de catering, en el celular, entre la cocina y un evento. Qué: cotizar, revisar stock, responder
clientes. Sensación: tranquila y confiable, como una cocina limpia antes del servicio.

## Tokens

### Color (roles en `apps/web/src/index.css`)
```
--color-primary: laurel (#2d6956)      acción principal, enlaces, foco
--color-primary-container: #d1e8dd     acceso destacado, selección en la navegación
--color-tertiary: cobre (#924b29)      acento puntual (≤ 10 %), nunca botones
--color-surface: #faf9f7               lienzo
--color-surface-container-lowest: #fff tarjetas y campos
--color-on-surface / -variant          texto principal / secundario
--color-outline-variant: #c4c7c4       bordes de tarjeta
--color-brand: #1f4d3f                 solo logo, login y theme-color
```

### Spacing
Base: 4 px (escala de Tailwind). Tarjeta: 16 px (20 px en escritorio). Entre tarjetas: 12 px. Entre secciones: 24 px.

### Radius
6 px campos y etiquetas · 8 px botones y navegación · 12 px tarjetas · 16 px cajón · 20 px tarjeta del login.

### Typography
Cuerpo: Roboto 400/500, raíz 17 px. Títulos de pantalla (`h1`): Bricolage Grotesque 600, 24 px (32 px escritorio),
tracking −0.015 em, `text-wrap: balance`. Cifras de tablas: `tabular-nums`.

## Patterns

### Button (`ui.tsx`)
- Alto mínimo 48 px (área táctil), relleno 20 px horizontal, radio 8 px, 17 px/500.
- Variantes: `primary` (relleno laurel), `tonal` (secondary-container), `secondary` (delineado), `ghost` (texto).

### Card (`ui.tsx`)
- Borde 1 px `outline-variant`, fondo `surface-container-lowest`, radio 12 px, relleno 16/20 px, sin sombra.

### Input (`inputClass`)
- Alto 48 px, borde 1 px `outline`, radio 6 px; foco: borde y anillo de 1 px `primary`.

### Status chip
- Radio 6 px, `px-2 py-0.5`, 15 px/500, colores del contenedor del estado.

## Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Laurel en vez de maqui | El usuario pidió colores distintos y un aspecto más profesional; laurel es una hierba de cocina y una tinta sobria | 2026-11-15 |
| Esquinas de 8 px en botones (antes píldora) | Las píldoras y los contenedores pastel eran el aspecto MD3 por defecto | 2026-11-15 |
| Estados con croma ≤ 22 | Los avisos no deben gritar más que la acción principal | 2026-11-15 |
| Borders-only | Herramienta de trabajo; las sombras no aportan información | 2026-11-15 |
| Se mantienen los nombres de rol MD3 | Cambiarlos tocaba todos los componentes sin cambiar lo que se ve | 2026-11-15 |
