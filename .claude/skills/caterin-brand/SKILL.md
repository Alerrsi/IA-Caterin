---
name: caterin-brand
description: Identidad visual de Cáterin (colores, tipografía, forma, logo, íconos y tono de los textos). Úsala al crear o cambiar cualquier pantalla, componente, ícono, PDF o material de la marca en apps/web o apps/api.
---

# Marca Cáterin

Fuentes de verdad: `docs/adr/ADR-008-identidad-visual.md` (color y logo) y `docs/adr/ADR-010-estetica-plano.md`
(estética "plano de cocina": tipografía, forma, líneas y detalles). Valores de diseño: `.interface-design/system.md`.
Esto es el resumen operativo. Manda sobre `interface-design`, `frontend-design`, `web-interface-guidelines` y
`emil-design-eng` cuando se contradicen.

## Dirección

"Cocina profesional ordenada", dibujada como un plano: la usuaria es una emprendedora de catering que cotiza desde el
celular entre un evento y otro. Herramienta tranquila y precisa: una sola tinta de marca (laurel), superficies casi
blancas, líneas finas como estructura, cifras como en una comanda y un acento cobre que aparece poco.

## Reglas

- **Roles de color, nunca hex.** Usa los roles de `apps/web/src/index.css` (`bg-primary`, `text-on-surface-variant`,
  `border-hairline`…). Los nombres vienen de Material Design 3 y se mantienen por compatibilidad.
- **Pares de contraste:** texto `on-X` sobre fondo `X`; en superficies, `on-surface` u `on-surface-variant`. Si usas un
  par nuevo, agrégalo a `PAIRS` en `src/theme.test.ts`.
- **Color:** semilla laurel `#1f4d3f`; terciaria cobre `#a0522d`. Para cambiar colores, edita `scripts/theme.mjs` y
  corre `npm run theme`; no edites el bloque `theme:start … theme:end` a mano.
- **Un acento.** `primary` es la acción; `tertiary` (cobre) solo para un ícono o detalle, nunca botones ni fondos
  grandes. Los estados (aviso, éxito, información, error) solo comunican estado.
- `brand`, `on-brand` y `brand-steam` son **solo** para el logo, el panel del login y la barra del sistema.
- **Tipografía (IBM Plex, autoalojada en `src/fonts.css`):**
  - Sans (variable) para toda la interfaz. Texto mínimo 15 px (`text-sm`); la única excepción son las etiquetas de la
    barra inferior.
  - Serif 500 (`font-display`) para `h1`, títulos de sección y destacados; cursiva 400 solo en la frase del login.
  - Mono 400 (clase `num` o `<Num>`) para cifras de comanda: precios, cantidades, stock, fechas, códigos y `kbd`.
  - No agregues pesos ni fuentes: el presupuesto de fuentes + marca es 200 KB (hoy 152 KB).
- **Forma:** esquinas casi rectas. `rounded-sm` 2 px etiquetas de estado y `kbd`; `rounded-md`/`rounded-lg` 4 px
  campos, botones y navegación; `rounded-xl` 6 px tarjetas, celdas y avisos; `rounded-2xl`/`rounded-3xl` 8 px cajón y
  tarjeta del login. `rounded-full` solo para botones de ícono circulares y el indicador de carga.
- **Líneas y profundidad:** tarjetas y divisores con `border-hairline`; bordes de campos con `outline` (3:1). Grillas
  de accesos y productos con `<Cells>` (líneas de 1 px, sin espacio). Línea de corte punteada
  (`border-dashed border-outline`) antes de un total y marco punteado en fotos de producto. Única sombra: la del botón
  (`shadow-key`, `shadow-cap`).
- **Fondos decorativos:** `grid-paper` (papel cuadriculado) en los márgenes del escritorio, el login y los vacíos;
  `hatch` (rayado) solo sobre el laurel del login. Nunca detrás de texto largo.
- **Marco:** en escritorio `Page` dibuja rieles a los lados y la línea de la cabecera con marcas (`frame-marks`).
  Toda pantalla con sesión usa `Page`.
- **Botones:** `<Button>` (48 px, tecla con borde inferior, baja 1 px al presionar). Atajos con `shortcut` o
  `aria-keyshortcuts` + `<Kbd>` (solo escritorio con mouse) y el hook `useShortcut` de `src/shortcuts.ts`; nunca
  actúan dentro de un campo. Hoy: `C` cotizar, `/` buscar.
- **Movimiento:** solo presión de botones, cajón y cambios de color; `ease-out` (curva fuerte) o `ease-drawer`, menos
  de 300 ms, propiedades explícitas (nunca `transition` a secas) y `motion-reduce:` siempre.
- **Logo:** usa `<Logo />`, `<Isotipo />` o `<AuthLayout>` de `components/Logo.tsx`. El dibujo es decorativo
  (`aria-hidden`); el nombre "Cáterin" va como texto en la serif. Cloche crema con vapor cobre sobre cuadrado laurel
  de esquina 96/512. Archivos en `public/brand/`; para cambiarlos, `scripts/brand.py` y `npm run icons`.
- **PDF de la cotización:** es de la pyme. El encabezado es el nombre (o logo) de la pyme; Cáterin solo firma al pie.
- **Íconos:** Material Icons rellenos, `viewBox` 24, en `components/Icon.tsx`. Comida: `cloche`, `restaurant`;
  pyme: `store`.
- **Un solo momento fuerte:** el panel laurel rayado del login. En las pantallas de trabajo manda la claridad.
- **Nada de Zed:** se tomaron principios, no su marca (sin su logo, textos, azul, fuentes ni diagramaciones).

## Textos

Español de Chile, simple, en segunda persona y con verbos concretos. El botón dice lo que pasa ("Cotizar con esta
pyme", no "Continuar"). Los errores dicen qué pasó y cómo seguir, sin disculpas. Puntos suspensivos con `…`.
Ejemplos:
- "Tu catering, ordenado y sin planillas"
- "Pega el mensaje del cliente y listo"
- "Esta pyme todavía no publica productos. Puedes escribirle tu pedido igual."

## Otras skills de diseño

- `interface-design`: dirección, jerarquía y revisión (`/interface-design:design-review`).
- `frontend-design`: solo para momentos de marca (login).
- `web-interface-guidelines`: detalles de interfaz. Excepciones en Cáterin: títulos y botones en mayúscula inicial
  del español, no *Title Case*; comillas y formatos de es-CL; `autoFocus` no se usa en el celular; `theme-color` es el
  laurel de la marca, no el fondo de la página.
- `emil-design-eng`: movimiento y sensación al presionar. Se implementa con CSS (no se agrega Motion); ignora su
  "Initial Response".

## Verificación

`npm test` (contraste, marca y `plano.test.tsx`), `npm run theme -- --check`, `npx playwright test e2e/a11y.e2e.ts
e2e/plano.e2e.ts` y capturas a 390 y 1280 px con `SHOTS=despues npx playwright test e2e/brand.e2e.ts`.
