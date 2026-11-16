# Design System — Cáterin

Memoria de la skill `interface-design`. Resumen de marca y reglas en `.claude/skills/caterin-brand/SKILL.md`;
decisión en `docs/adr/ADR-013-estetica-de-la-referencia.md` (T21, 16-nov-2026; reemplaza ADR-008 y ADR-010). Los
colores salen de `apps/web/scripts/theme.mjs` (paleta declarada a mano; no se escriben en el CSS).

## Direction

**Personality:** cálida y apetitosa, como la imagen de referencia de una app de comida: blanco limpio, tinta casi negra,
panel oscuro en diagonal con dibujos de comida, platos redondos enormes y un acento amarillo.
**Foundation:** blanco `#ffffff` sobre lienzo `#f7f6f3`.
**Depth:** sombras suaves y difusas (`shadow-cap`, `shadow-soft`, `shadow-plate`); sin bordes finos en las tarjetas.

Quién: emprendedora de catering (y sus clientes en el portal), en el celular. Qué: cotizar, revisar stock, responder
clientes. Sensación: dan ganas de comer; ordenado y simple.
Firma: plato redondo que se sale del panel oscuro, título en dos pesos, píldora negra con círculo amarillo, tarjeta
punteada tipo cupón, barra inferior flotante oscura.

## Tokens

### Color (roles en `apps/web/src/index.css`)
```
--color-primary: #1a1a1a                  botón principal, enlaces, selección
--color-accent: #ffd45c                   SOLO fondo: círculo del ícono, chips, activo de la barra, botón tonal
--color-on-accent: #1a1a1a                texto sobre amarillo
--color-accent-soft: #fff4cf              hover de tarjetas, contenedores suaves
--color-tertiary: #7a5200                 acento cálido como texto/ícono sobre blanco (AA)
--color-panel: #1b1b1b                    panel oscuro de las portadas (con `doodles`)
--color-on-panel / on-panel-variant       texto sobre el panel
--color-surface-container-low: #f7f6f3    lienzo de la página
--color-surface-container-lowest: #fff    tarjetas y campos
--color-outline: #85827b                  borde de campos (3:1)
--color-brand: #1a1a1a                    logo y theme-color
--color-chart-1 / chart-2: #d99a00 / #5a5ad6  gráficos (validados con dataviz)
```

### Spacing
Base 4 px. Tarjeta: 16–24 px. Entre bloques: 24 px. Portadas: 24–48 px de relleno.

### Radius
8 px chips de estado y `kbd` · 14 px campos · píldora (`rounded-lg` = 9999 px) botones y navegación · 22 px tarjetas ·
28–36 px portadas y cajón.

### Typography (Urbanist variable)
Interfaz 500, raíz 17 px, mínimo 15 px. `h1` 800, 32 px (44 px escritorio), interletra −0,025 em. Títulos de portada
en dos pesos (400 arriba, 800 abajo) hasta 60 px. `h2` 700. Cifras: misma fuente, 700, `tabular-nums` (`.num`).

### Motion
`--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` (150 ms, presión, color, opacidad); `--ease-drawer` (300 ms, cajón).
`motion-reduce` quita el desplazamiento.

## Patterns

### Button (`ui.tsx`)
- Píldora de 48 px mínimo, 17 px/600. `primary` negro + `shadow-key`; `tonal` amarillo; `secondary` blanco delineado;
  `ghost` texto. `icon="…"`: círculo amarillo de 36 px al inicio (negro con ícono amarillo en el `tonal`).

### Food (`components/Food.tsx`)
- `FoodPanel`: panel `bg-panel doodles`, corte diagonal (abajo en el celular, izquierda desde `lg`).
- `Plate`: foto recortada en círculo con `shadow-plate`; sin foto, un plato dibujado (empanadas).
- `Floater`: ingrediente con sombra; sin foto, uno dibujado. `Coupon`: borde punteado de 2 px, título con línea punteada.

### Cells (`ui.tsx`, utilidad `cells`)
- Grilla con 12–16 px de aire; cada `<li>` es una tarjeta blanca, radio 22 px, `shadow-cap`. Accesos con `IconDot`.

### Page (`ui.tsx`)
- Volver en un círculo blanco con sombra; título grande (opcional `lead` en 400 arriba); bajada y acciones.

### AppShell
- Escritorio: barra superior blanca (logo, destinos en píldora, "Más", "Cerrar sesión" delineado).
- Celular: barra superior + barra inferior flotante oscura con el activo en círculo amarillo.

### Input (`inputClass`)
- 48 px, borde `outline`, radio 14 px; foco: borde negro y halo amarillo.

### Status chip
- Píldora de 32 px, 15 px/600, colores del contenedor del estado.

## Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Estética de la imagen de referencia en toda la app (ADR-013) | El usuario: "yo no veo el diseño como el de la foto"; eligió toda la app, muy fiel y fotos libres | 2026-11-16 |
| Urbanist en vez de IBM Plex | Geométrica como la de la referencia; una sola variable de ≈ 28 KB | 2026-11-16 |
| Amarillo solo como fondo | 1,4:1 sobre blanco: como texto no pasa AA | 2026-11-16 |
| Paleta declarada a mano en `theme.mjs` | La referencia no sale de una semilla MD3; se mantienen los nombres de rol | 2026-11-16 |
| Píldoras en botones y navegación; tarjetas de 22 px | Así se ve la referencia | 2026-11-16 |
| Reemplazos dibujados para fotos que faltan | La composición no se rompe sin red ni antes de cargar fotos | 2026-11-16 |
| Atajos solo `C` y `/` (de T16) | Los que más se repiten en escritorio; nunca dentro de un campo | 2026-11-15 |
