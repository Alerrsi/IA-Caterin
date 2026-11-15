---
name: caterin-brand
description: Identidad visual de Cáterin (colores, tipografía, logo, íconos y tono de los textos). Úsala al crear o cambiar cualquier pantalla, componente, ícono, PDF o material de la marca en apps/web o apps/api.
---

# Marca Cáterin

Fuente de verdad: `docs/adr/ADR-008-identidad-visual.md`. Esto es el resumen operativo.

## Reglas

- **Material Design 3 siempre.** Usa los roles de color de `apps/web/src/index.css` (`bg-primary`,
  `text-on-surface-variant`, `bg-surface-container-lowest`…). Nunca escribas un hex en un componente.
- **Pares de contraste:** texto `on-X` sobre fondo `X`; en superficies, `on-surface` u `on-surface-variant`. Si usas un
  par nuevo, agrégalo a `PAIRS` en `src/theme.test.ts`.
- **Color:** semilla maqui `#6d2a57` (baya de La Araucanía); acento terciario verde araucaria. Para cambiar colores,
  edita `scripts/theme.mjs` y corre `npm run theme`; no edites el bloque `theme:start … theme:end` a mano.
- `brand`, `on-brand` y `brand-steam` son **solo** para el logo, el panel del login y la barra del sistema. El resto
  de la interfaz usa `primary` y compañía.
- **Tipografía:** los `h1` usan Bricolage Grotesque (`font-display`, seminegrita); el resto, Roboto 400/500. No
  agregues otras fuentes ni CDN: todo va autoalojado en `src/fonts.css` para funcionar sin red.
- **Logo:** usa `<Logo />`, `<Isotipo />` o `<AuthLayout>` de `components/Logo.tsx`. El dibujo es decorativo
  (`aria-hidden`); el nombre "Cáterin" va como texto. No deformes, no cambies colores ni agregues efectos. Archivos
  sueltos en `public/brand/`; para cambiarlos, `scripts/brand.py` y `npm run icons`.
- **PDF de la cotización:** es de la pyme. El encabezado es el nombre (o logo) de la pyme; Cáterin solo firma al pie.
- **Íconos:** Material Icons rellenos, `viewBox` 24, agregados en `components/Icon.tsx`. Comida: `cloche`,
  `restaurant` (cubiertos); pyme: `store`.
- **Forma:** `rounded-md` campos, `rounded-lg` chips, `rounded-xl` tarjetas, `rounded-2xl` cajón, `rounded-3xl`
  diálogos, `rounded-full` botones (tokens MD3 en `index.css`).
- **Un solo momento fuerte:** el panel maqui del login. No repitas fondos de marca, degradados ni ilustraciones en las
  pantallas de trabajo; ahí manda la claridad.

## Textos

Español de Chile, simple, en segunda persona y con verbos concretos. El botón dice lo que pasa ("Cotizar con esta
pyme", no "Continuar"). Los errores dicen qué pasó y cómo seguir, sin disculpas. Ejemplos:
- "Tu catering, ordenado y sin planillas"
- "Pega el mensaje del cliente y listo"
- "Esta pyme todavía no publica productos. Puedes escribirle tu pedido igual."

## Verificación

`npm test` (contraste y marca), `npx playwright test e2e/a11y.e2e.ts` (axe) y capturas con
`SHOTS=despues npx playwright test e2e/brand.e2e.ts`.
