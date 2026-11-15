# T14 — Identidad visual de catering sobre Material Design 3
- Estado: hecha (falta la prueba de 5 segundos con personas reales)
- Depende de: T08
- Funcionalidad: transversal

## Objetivo
Que la emprendedora y sus clientes reconozcan de un vistazo que Cáterin es un software de catering: color, tipografía,
logo e íconos propios, sin dejar Material Design 3 y sin perder accesibilidad ni el funcionamiento sin red.

## Contexto y decisiones previas
- Plan: `docs/RENOVACION.md` (secciones 4 y 9). Decisión: [ADR-008](../adr/ADR-008-identidad-visual.md).
- Supuestos explícitos (el usuario delegó los detalles el 15-nov-2026; los datos son de una pyme ficticia):
  semilla maqui `#6d2a57`, terciaria araucaria `#3f5f3a`, Bricolage Grotesque para títulos, cloche con vapor como logo.
- Se revisó la dirección con la skill `frontend-design` antes de construir: la primera idea (terracota, crema, serif)
  es el rasgo n.º 1 de su lista de valores por defecto y se cambió.

## Entregables
- [x] Skills `material-3` y `frontend-design` revisadas e instaladas con commit fijo (`.claude/skills/SOURCES.md`).
- [x] Generador de tema `apps/web/scripts/theme.mjs` (`npm run theme`, `--check`) y nuevo `@theme` en `index.css`.
- [x] Prueba de contraste AA de cada par texto/fondo (`src/theme.test.ts`, 46 casos).
- [x] Fuentes autoalojadas (`src/fonts.css`) y en el precaché de la PWA.
- [x] Logo: isotipo, maskable, monocromo, logotipo horizontal (y en blanco) y apilado en `public/brand/`
      (`scripts/brand.py`); PNG de la PWA, `apple-touch-icon` y favicon (`scripts/icons.mjs`, `npm run icons`).
- [x] Manifiesto con íconos `any` y `maskable` separados, `theme-color` maqui en `index.html` y el manifiesto.
- [x] `components/Logo.tsx` (`Isotipo`, `Logo`, `AuthLayout`) en login, crear cuenta, registro de cliente, cabecera y
      cajón (todas las pantallas con sesión, también las del cliente).
- [x] PDF: colores de la marca y pie "Hecha con Cáterin" con el isotipo monocromo (`apps/api/app/assets/`).
- [x] Íconos cloche, cubiertos, tienda, buscar, check y foto en `Icon.tsx`.
- [x] Esquinas: clases `rounded-*` mapeadas a los tokens de forma MD3.
- [x] Auditoría MD3 (abajo) y capturas antes/después.
- [x] Skill del proyecto `.claude/skills/caterin-brand/SKILL.md`.
- [ ] Prueba de 5 segundos con al menos 5 personas (requiere personas reales; ver riesgos).

## Criterios de aceptación
| Criterio | Cómo se verifica | Resultado |
|---|---|---|
| Roles y componentes MD3 de `ui.tsx` se mantienen | `git diff` de `ui.tsx`: solo el peso del título | Cumple |
| Contraste AA | `npx vitest run src/theme.test.ts`; `npx playwright test e2e/a11y.e2e.ts` | 46/46 pares ≥ 4.5:1; axe sin violaciones serias en login, registro y 10 pantallas |
| PWA instalable y fuentes sin red | `PWA_BASE_URL=… npx playwright test e2e/pwa.e2e.ts` (build + `vite preview`) | Manifiesto con `any` y `maskable`; Roboto y Bricolage cargan sin red |
| Peso de fuentes e íconos ≤ 200 KB | `du -b` de `dist/` tras `vite build` | 168,6 KB (fuentes 85,4 KB) |
| Logo en login, cabecera, inicio del cliente y PDF | Capturas `e2e-artifacts/despues/` (`SHOTS=despues npx playwright test e2e/brand.e2e.ts`); prueba del PDF | Cumple |
| Un cliente nuevo reconoce el rubro en el login | Prueba de 5 segundos | **Pendiente, no medido** |

## Pruebas requeridas
- `src/theme.test.ts`: contraste de cada par.
- `src/brand.test.tsx`: logo accesible, `theme-color` coherente, íconos de la PWA, tema generado al día.
- `e2e/pwa.e2e.ts`: manifiesto y fuentes sin red. `e2e/a11y.e2e.ts`: axe. `e2e/brand.e2e.ts`: capturas.
- `tests/test_quotes_api.py`: el PDF lleva el pie "Hecha con Cáterin" y sigue sin datos internos.

## Auditoría MD3 (`/material-3 audit`, sobre el código, 15-nov-2026)

| Categoría | Puntaje | Estado | Nota |
|---|---|---|---|
| Color tokens | 9/10 | pass | Todo por roles; sin hex en componentes; pares on-X/X probados. Sin modo oscuro (fuera de alcance) |
| Typography | 6/10 | warn | Display para títulos y Roboto para el cuerpo, pero los tamaños son clases de Tailwind, no la escala MD3 (`display/headline/title/body/label`) |
| Shape | 8/10 | pass | Esquinas mapeadas a tokens MD3 (corregido en esta tarea); botones `full`, tarjetas `medium` |
| Elevation | 7/10 | pass | Elevación tonal con `surface-container-*`; quedan 5 `shadow` (hover de tarjetas, cajón modal) |
| Components | 7/10 | pass | HTML propio con la anatomía MD3 (botón relleno, tonal, de texto; campo con contorno; barra de navegación) sin `@material/web` (decisión de T08) |
| Layout | 8/10 | pass | Ancho máximo de contenido (`max-w-3xl`/`6xl`), mobile-first, sin scroll horizontal a 390 px |
| Navigation | 6/10 | warn | Barra inferior en celular y cajón fijo desde 1024 px; entre 600 y 1024 px MD3 recomienda un *navigation rail* |
| Motion | 5/10 | warn | Casi sin movimiento; sin tokens de easing/duración |
| Accessibility | 9/10 | pass | axe AA, objetivos táctiles de 48 px o más, foco visible, logo con nombre en texto |
| Theming | 8/10 | pass | Propiedades en `@theme` generadas desde la semilla; `npm run theme -- --check` en las pruebas |

Total: 73/100. Las advertencias (escala tipográfica como tokens, *navigation rail* en tablet y tokens de movimiento)
quedan como mejoras: no afectan al objetivo de la tarea y cambiarían la estructura de los componentes, que el plan
dejó fija.

## Fuera de alcance
- Modo oscuro. Cambiar de MD3. Rediseñar la estructura de las pantallas.

## Riesgos y preguntas abiertas
- **La marca no está validada con personas.** Falta la prueba de 5 segundos (`docs/RENOVACION.md` 4.6) y mostrarla a la
  dueña de una pyme real. Cambiar la semilla o el logo es barato (`npm run theme`, `scripts/brand.py`).
- `brand.py` necesita fontTools fuera del proyecto; si se pierde la fuente de `node_modules` hay que reinstalar.

## Resumen de cierre
Se pasó de un panel gris a una identidad de catering: maqui con acento araucaria, Bricolage Grotesque en títulos, logo
de cloche con vapor en todas las pantallas, login con el panel de la marca, íconos de PWA correctos (antes el
*maskable* se recortaba) y fuentes que funcionan sin red. Todo verificado con pruebas automáticas (contraste, marca,
PWA, axe y PDF). Pendiente: prueba de 5 segundos con personas y las mejoras de la auditoría MD3.
