---
name: caterin-brand
description: Identidad visual de Cáterin (colores, tipografía, forma, logo, íconos y tono de los textos). Úsala al crear o cambiar cualquier pantalla, componente, ícono, PDF o material de la marca en apps/web o apps/api.
---

# Marca Cáterin

Fuente de verdad: `docs/adr/ADR-013-estetica-de-la-referencia.md` (T21, 16-nov-2026), que reemplaza a ADR-008
(laurel y cobre) y ADR-010 ("plano de cocina"). Valores de diseño: `.interface-design/system.md`. Esto es el resumen
operativo. Manda sobre `interface-design`, `frontend-design`, `web-interface-guidelines` y `emil-design-eng` cuando se
contradicen.

## Dirección

La estética de la imagen de referencia que eligió el usuario: una app de **comida** que da hambre, no una planilla.
Blanco limpio, tinta casi negra, un gran panel oscuro en diagonal con dibujos de comida en línea fina, platos redondos
enormes vistos desde arriba, ingredientes que flotan, títulos grandes en dos pesos y botones en píldora con un círculo
amarillo. Fuerte en entrar, inicio y portal; sobria (los mismos tokens) en formularios y tablas.

## Reglas

- **Roles de color, nunca hex.** Usa los roles de `apps/web/src/index.css` (`bg-primary`, `text-on-surface-variant`,
  `bg-accent`, `bg-panel`…). Para cambiar un color, edita `scripts/theme.mjs` (paleta declarada a mano) y corre
  `npm run theme`; no edites el bloque `theme:start … theme:end`.
- **Pares de contraste:** texto `on-X` sobre fondo `X`. Si usas un par nuevo, agrégalo a `PAIRS` en
  `src/theme.test.ts`.
- **Colores:** tinta `#1a1a1a` (`primary`, `brand`) para el botón principal, enlaces y selección; blanco y lienzo
  `#f7f6f3`; panel `#1b1b1b` con `on-panel`/`on-panel-variant`.
- **El amarillo `#ffd45c` (`accent`) solo es fondo:** círculo del ícono del botón, chips (`<Pill>`), el destino activo
  de la barra inferior, el botón `tonal`. Su texto es `on-accent` (negro). **Nunca** amarillo como texto sobre blanco
  (1,4:1; hay una prueba que lo recuerda). Para un acento cálido sobre blanco, `tertiary` (ámbar oscuro).
- **Tipografía:** Urbanist variable autoalojada (`src/fonts.css`). Interfaz en 500; títulos grandes en **dos pesos**:
  arriba 400 y abajo 800 (`<Page lead=… title=…>` o dos `span`). Cifras con la clase `num` o `<Num>` (cifras
  tabulares, 700). No agregues fuentes.
- **Forma:** `rounded-lg` es **píldora** (botones, chips, navegación); `rounded-md` 14 px campos; `rounded-xl` 22 px
  tarjetas y avisos; `rounded-2xl`/`rounded-3xl` 28–36 px portadas y cajón. Botones circulares con `rounded-full`.
- **Profundidad:** sombras suaves y difusas: `shadow-cap` (tarjetas), `shadow-key` (botón principal), `shadow-soft`
  (portadas y flotantes), `shadow-plate` (platos). Sin bordes finos alrededor de las tarjetas.
- **Piezas de comida (`components/Food.tsx`):** `FoodPanel` (panel oscuro con `doodles` y corte diagonal: abajo en el
  celular, a la izquierda desde `lg`), `Plate` (plato redondo; si la foto falta, uno dibujado), `Floater`
  (ingrediente flotando), `Coupon` (tarjeta punteada tipo cupón) y `Squiggle`. Fotos en `public/fotos/` (licencia
  libre, ver `THIRD_PARTY_NOTICES.md`); las de productos llegan por `photo_url`.
- **Fondos:** `doodles` (dibujos de comida claros) solo sobre `bg-panel`; `grid-paper` (los mismos, muy tenues) en
  vacíos. Nunca detrás de texto largo.
- **Botones:** `<Button>` (48 px mínimo, píldora). `icon="…"` pone el ícono en un círculo amarillo, como el "Buy Now"
  de la referencia; úsalo en la acción principal de una portada. Variantes: `primary` negro, `tonal` amarillo,
  `secondary` delineado, `ghost` texto. Foco: anillo oscuro (`ring-primary/40`); sobre el panel, `ring-accent`.
- **Marco:** en escritorio, barra superior blanca con el logo, los destinos en píldora, "Más" (cajón) y "Cerrar sesión"
  delineado. En el celular, barra superior con menú y barra inferior **flotante oscura**; el activo lleva el círculo
  amarillo. Toda pantalla con sesión usa `Page` (salvo el inicio, que tiene portada propia).
- **Atajos:** `shortcut` o `aria-keyshortcuts` + `<Kbd>` (solo escritorio con mouse) y `useShortcut`; nunca actúan
  dentro de un campo. Hoy: `C` cotizar, `/` buscar.
- **Movimiento:** solo presión de botones, cajón y cambios de color/opacidad; `ease-out` o `ease-drawer`, menos de
  300 ms, propiedades explícitas y `motion-reduce:` siempre.
- **Logo:** `<Logo />`, `<Isotipo />` o `<AuthLayout>` de `components/Logo.tsx`. Cloche blanca con vapor amarillo
  sobre cuadrado de tinta (esquina 120/512); la palabra "Cáterin" va como texto en Urbanist 800. Archivos en
  `public/brand/`; para cambiarlos, `scripts/brand.py` y `npm run icons`.
- **PDF de la cotización:** es de la pyme. El encabezado es el nombre (o logo) de la pyme; Cáterin solo firma al pie.
- **Íconos:** Material Icons rellenos, `viewBox` 24, en `components/Icon.tsx`.
- **Sin precios inventados:** en el portal el precio sale al cotizar (ADR-009); nada de precios tachados si no existe
  un precio anterior real.
- **Nada de la marca de la referencia:** se tomaron rasgos visuales, no su logo, nombre ni textos.

## Textos

Español de Chile, simple, en segunda persona y con verbos concretos. El botón dice lo que pasa ("Cotizar con esta
pyme", no "Continuar"). Los errores dicen qué pasó y cómo seguir, sin disculpas. Puntos suspensivos con `…`.
Ejemplos:
- "Tu catering, / **ordenado y sin planillas**"
- "Hola, Marta / **¿Qué cotizamos hoy?**"
- "Esta pyme todavía no publica productos. Puedes escribirle tu pedido igual."

## Otras skills de diseño

- `interface-design`: dirección, jerarquía y revisión (`/interface-design:design-review`).
- `frontend-design`: para portadas y momentos de marca.
- `web-interface-guidelines`: detalles de interfaz. Excepciones en Cáterin: títulos y botones en mayúscula inicial
  del español, no *Title Case*; comillas y formatos de es-CL; `autoFocus` no se usa en el celular; `theme-color` es la
  tinta de la marca.
- `emil-design-eng`: movimiento y sensación al presionar. Se implementa con CSS (no se agrega Motion).
- `dataviz`: colores de gráficos `chart-1` (dorado `#d99a00`) y `chart-2` (índigo `#5a5ad6`), validados con su script.

## Verificación

`npm test` (contraste, marca y `estetica.test.tsx`), `npm run theme -- --check`, `npx playwright test e2e/a11y.e2e.ts
e2e/estetica.e2e.ts` y capturas a 390 y 1280 px con `npx playwright test e2e/t21.e2e.ts` (en `e2e-artifacts/t21/`).
