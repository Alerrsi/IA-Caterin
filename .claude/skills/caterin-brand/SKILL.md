---
name: caterin-brand
description: Identidad visual de Cáterin (colores, tipografía, forma, logo, íconos y tono de los textos). Úsala al crear o cambiar cualquier pantalla, componente, ícono, PDF o material de la marca en apps/web o apps/api.
---

# Marca Cáterin

Fuente de verdad: `docs/adr/ADR-008-identidad-visual.md`. Valores de diseño (espaciado, forma, patrones de
componentes): `.interface-design/system.md`. Esto es el resumen operativo. Manda sobre `interface-design` y
`frontend-design` cuando se contradicen.

## Dirección

"Cocina profesional ordenada": la usuaria es una emprendedora de catering que cotiza desde el celular entre un evento
y otro. La interfaz es una herramienta de trabajo tranquila y confiable: una sola tinta de marca (laurel), superficies
casi blancas y un acento cobre que aparece poco.

## Reglas

- **Roles de color, nunca hex.** Usa los roles de `apps/web/src/index.css` (`bg-primary`, `text-on-surface-variant`,
  `bg-surface-container-lowest`…). Los nombres vienen de Material Design 3 y se mantienen por compatibilidad; la guía
  de diseño ya no es MD3.
- **Pares de contraste:** texto `on-X` sobre fondo `X`; en superficies, `on-surface` u `on-surface-variant`. Si usas un
  par nuevo, agrégalo a `PAIRS` en `src/theme.test.ts`.
- **Color:** semilla laurel `#1f4d3f`; terciaria cobre `#a0522d`. Para cambiar colores, edita `scripts/theme.mjs` y
  corre `npm run theme`; no edites el bloque `theme:start … theme:end` a mano.
- **Un acento.** `primary` es la acción; `tertiary` (cobre) solo para un ícono o detalle que deba distinguirse, nunca
  para botones ni fondos grandes. Los estados (aviso, éxito, información, error) solo comunican estado.
- `brand`, `on-brand` y `brand-steam` son **solo** para el logo, el panel del login y la barra del sistema.
- **Forma:** esquinas contenidas, no píldoras. `rounded-md` (6 px) campos y etiquetas de estado, `rounded-lg` (8 px)
  botones, chips y navegación, `rounded-xl` (12 px) tarjetas y avisos, `rounded-2xl` cajón, `rounded-3xl` (20 px)
  tarjeta del login. `rounded-full` solo para botones de ícono circulares y el indicador de carga.
- **Profundidad:** bordes suaves (`outline-variant`) y cambios de superficie; sin sombras marcadas ni degradados.
- **Tipografía:** los `h1` usan Bricolage Grotesque (`font-display`, seminegrita); el resto, Roboto 400/500. Cifras en
  tablas con `tabular-nums`. No agregues otras fuentes ni CDN: todo va autoalojado en `src/fonts.css`.
- **Logo:** usa `<Logo />`, `<Isotipo />` o `<AuthLayout>` de `components/Logo.tsx`. El dibujo es decorativo
  (`aria-hidden`); el nombre "Cáterin" va como texto. Cloche crema con vapor cobre sobre cuadrado laurel. Archivos en
  `public/brand/`; para cambiarlos, `scripts/brand.py` y `npm run icons`.
- **PDF de la cotización:** es de la pyme. El encabezado es el nombre (o logo) de la pyme; Cáterin solo firma al pie.
- **Íconos:** Material Icons rellenos, `viewBox` 24, en `components/Icon.tsx`. Comida: `cloche`, `restaurant`;
  pyme: `store`.
- **Un solo momento fuerte:** el panel laurel del login. En las pantallas de trabajo manda la claridad.

## Textos

Español de Chile, simple, en segunda persona y con verbos concretos. El botón dice lo que pasa ("Cotizar con esta
pyme", no "Continuar"). Los errores dicen qué pasó y cómo seguir, sin disculpas. Ejemplos:
- "Tu catering, ordenado y sin planillas"
- "Pega el mensaje del cliente y listo"
- "Esta pyme todavía no publica productos. Puedes escribirle tu pedido igual."

## Verificación

`npm test` (contraste y marca), `npm run theme -- --check`, `npx playwright test e2e/a11y.e2e.ts` (axe) y capturas
con `SHOTS=despues npx playwright test e2e/brand.e2e.ts`. Revisión de oficio: `/interface-design:design-review`.
