# ADR-008 — Identidad visual de Cáterin

- Estado: **aceptado** (15-nov-2026, pedido del usuario; plan en `docs/RENOVACION.md`, tarea T14).
  **Revisado** el mismo día: colores, forma y skills (sección "Revisión: laurel e `interface-design`"). Los puntos
  2, 5 (colores del logo), 9 y 10 quedan reemplazados por esa revisión. La tipografía (punto 4), la forma y el
  logotipo cambian otra vez con [ADR-010](ADR-010-estetica-plano.md) (IBM Plex, esquinas de 2–8 px).
- Contexto en: T08 (frontend PWA), ADR-004 (offline), AGENTS.md (WCAG AA, mobile-first).

## Contexto

La app usaba Material Design 3 con un esquema neutro gris (`#3d4449`), sin logo en pantalla y con Roboto solo
nombrada (no incluida). Se veía como un panel de administración genérico, sin pistas de comida ni eventos. El usuario
pidió "mejor diseño con logos" que transmita que es un software de catering, **sin dejar MD3** y usando skills de
diseño para el agente. El usuario delegó las decisiones de detalle (15-nov-2026: "usa los detalles a tu criterio";
los datos son de una pyme ficticia de demo).

## Decisión

1. **Se mantiene MD3 y su estructura.** Cambian los tokens (color, tipografía, forma), el logo, algunos íconos y el
   marco de las pantallas sin sesión. Los componentes de `ui.tsx` siguen usando roles (`primary`,
   `surface-container`, `on-surface-variant`…); solo cambió el peso del título de pantalla.
2. **Color semilla: maqui `#6d2a57`**, la baya nativa de La Araucanía. Se descartó la primera idea (terracota con
   fondo crema y serif de display): la skill `frontend-design` la lista como el primer rasgo de las interfaces
   generadas por IA. El maqui es comida local, no se confunde con el rojo de error y da identidad propia.
   - Paletas armadas con `@material/material-color-utilities` 0.3.0 en `apps/web/scripts/theme.mjs`
     (`npm run theme`): primaria con croma 48, secundaria recesiva del mismo tono (croma 16), **terciaria verde
     araucaria** (`#3f5f3a`) como acento, neutros con croma 2 y 5. Los estados aviso, éxito e información se
     armonizan con la semilla (`Blend.harmonize`, croma máximo 32).
   - Tokens de marca aparte: `brand` (maqui puro), `on-brand`, `brand-steam`. Solo para el logo, la barra del
     sistema (`theme-color`) y el panel del login.
   - La 0.4.0 de la librería publica ESM sin extensiones y no corre en Node; por eso la 0.3.0.
3. **Contraste verificado por código:** `src/theme.test.ts` calcula el contraste WCAG de cada par texto/fondo que usa
   la app (mínimo 4.5:1; 3:1 para el contorno de campos). `src/brand.test.tsx` falla si `index.css` no coincide con
   el generador.
4. **Tipografía autoalojada** (`src/fonts.css`): Roboto 400 y 500 para el cuerpo y **Bricolage Grotesque** (variable)
   para títulos y el logotipo, solo el subconjunto latino en `woff2`, licencia OFL. Se descartó una serif de display
   por la misma razón que el terracota. Los `woff2` entran al precaché (`workbox.globPatterns`), así que funcionan
   sin red. Peso medido en el `build`: 85 KB de fuentes, 169 KB con íconos y SVG de marca (presupuesto: 200 KB).
5. **Logo: cloche con vapor**, "comida caliente lista para servir", sobre el cuadrado maqui. Sale de la cloche que ya
   tenía `icon.svg`. Lo genera `apps/web/scripts/brand.py` (el logotipo en trazos con fontTools) y los PNG
   `scripts/icons.mjs` con el Chromium de Playwright, sin agregar librerías nativas:
   - `public/brand/`: isotipo, isotipo maskable (fondo completo, dibujo al 72 % dentro de la zona segura), monocromo
     calado, logotipo horizontal (y en blanco) y apilado.
   - PWA: `pwa-192.png` y `pwa-512.png` (`any`), `pwa-maskable-512.png` (`maskable`), `apple-touch-icon.png` y
     `favicon-64.png`. Antes el SVG se declaraba `any maskable` sin cumplir la zona segura.
   - `theme-color` maqui, igual en `index.html` y el manifiesto (lo prueba `brand.test.tsx`).
6. **Dónde aparece:** marco de las pantallas sin sesión (`AuthLayout`: login, crear cuenta, registro de cliente), con
   el único "momento fuerte" de la marca (panel maqui con la cloche grande); cabecera y cajón de `AppShell` (logo
   horizontal, en todas las pantallas con sesión, también las del cliente).
7. **PDF de la cotización:** es de la pyme para su cliente, así que el encabezado sigue siendo el nombre de la pyme.
   Cambian los colores a los de la marca y al pie va "Hecha con Cáterin" con el isotipo monocromo (PNG en
   `apps/api/app/assets/`, porque ReportLab no dibuja SVG).
8. **Íconos:** se agregan cloche, cubiertos, tienda, buscar, check y foto de Material Icons (Apache-2.0); Recetas
   usa cubiertos en vez del libro.
9. **Forma:** las clases `rounded-*` de Tailwind se mapean a los tokens de esquina MD3 en px (`index.css`).
10. **Skills de diseño** en `.claude/skills/`: `material-3` (MIT, commit `14385f2`) y `frontend-design`
    (Apache-2.0, commit `1780c5e`), copiadas tras revisar su `SKILL.md` (solo Markdown, sin scripts); origen en
    `.claude/skills/SOURCES.md`. Más una skill propia, `caterin-brand`, con las reglas de esta decisión.

## Consecuencias

- Cambiar la marca es repetible: semilla en `theme.mjs` → `npm run theme`; dibujo en `brand.py` → `npm run icons`.
- `brand.py` necesita fontTools, que no es dependencia del proyecto (solo al rediseñar el logotipo).
- Sin modo oscuro (fuera de alcance); el generador puede producirlo cambiando `isDark`.
- **No se ha medido** si una persona reconoce el rubro en el login: la prueba de 5 segundos de `docs/RENOVACION.md` (4.6)
  queda pendiente porque requiere personas reales. No se reporta como cumplida.
- Auditoría MD3 y sus pendientes: ver `docs/tasks/T14-identidad-visual.md`.

## Revisión: laurel e `interface-design` (15-nov-2026)

**Pedido del usuario:** "quiero que los colores sean diferentes; si ves pertinente cambia la skill de material design
por otra que se vea más profesional".

**Decisión:**

1. **Skill:** se retira `material-3` y entra **`interface-design`** (Dammyjay93, MIT, commit `2f9be32`), pensada para
   herramientas de gestión ("dashboards, admin panels, SaaS apps, tools"), que es lo que es Cáterin. Pide decidir
   intención, jerarquía, profundidad y escala antes de escribir UI, y trae `/interface-design:design-review` y
   `/interface-design:design-deslop`. Su memoria es `.interface-design/system.md`. `frontend-design` se queda para los
   momentos de marca (login). Descartadas y por qué: `.claude/skills/SOURCES.md`.
2. **Color:** semilla **laurel `#1f4d3f`** (hierba de cocina, tinta sobria) en vez de maqui. Primaria con croma 30
   (`#2d6956`), contenedores de la primaria con croma 14 (sin menta chillón), secundaria croma 10, **terciaria cobre**
   (`#a0522d`, las ollas) como único acento cálido, neutros del mismo tono con croma 2 y 4 (`surface` `#faf9f7`: casi
   blanco, sin crema). Estados armonizados con croma máximo 22 (antes 32) para que los avisos no compitan con la
   acción principal. Mismo generador (`npm run theme`) y misma prueba de contraste: 41 pares en AA y el contorno de los campos en 3:1.
3. **Logo:** misma cloche; cuadrado laurel, cloche casi blanca y vapor cobre claro. `theme-color` `#1f4d3f`. PDF:
   títulos laurel y franjas `#f5f3f1`.
4. **Forma:** botones, chips y navegación con esquina de 8 px en vez de píldora; campos y etiquetas de estado 6 px;
   tarjeta del login 20 px (antes 28). Se quitó el `tracking-wide` de los botones (rasgo MD3).
5. **Detalles:** `h1` con tracking −0.015 em y `text-wrap: balance` (también `h2`); tablas con `tabular-nums`.
6. **Se mantienen** los nombres de rol MD3 en `index.css` (`primary`, `surface-container`…): renombrarlos tocaba todos
   los componentes sin cambiar lo que se ve. La estructura de `ui.tsx` no cambia; solo clases de forma.

**Consecuencias:** el éxito (`success`, verde) queda cerca de la primaria; siempre va con texto o ícono, no solo color.
La tipografía de títulos (Bricolage Grotesque) se mantiene: si se quiere un aspecto aún más sobrio, el siguiente paso
es cambiarla y regenerar el logotipo con `brand.py`. Sigue sin validarse con personas reales.
