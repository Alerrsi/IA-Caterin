# T16 — Estética "plano de cocina": detalles inspirados en zed.dev
- Estado: hecha en la rama (15-nov-2026); falta que el usuario revise las capturas para integrarla a `main`
- Rama: `feat/T16-estetica-plano`
- Depende de: T14 (identidad visual, ADR-008), T15 (catálogo)
- Funcionalidad: transversal
- Decisión: [ADR-010](../adr/ADR-010-estetica-plano.md) (aceptado)

## Objetivo
Que Cáterin se vea como una herramienta hecha con oficio: ordenada, precisa y confiable, como una cocina profesional
antes del servicio. Se toman los **principios** de la estética de zed.dev (líneas finas, tipografía con carácter,
números en monoespaciada, esquinas casi rectas, un solo acento) y se traducen al mundo del catering, sin copiar la
marca de Zed.

## Contexto y decisiones previas
- Pedido del usuario (15-nov-2026): "busca integrar detalles o la estética de https://zed.dev/ en otra rama; primero
  crea un plan de implementación del diseño; agrega skills que consideres necesarias".
- Base al empezar: paleta laurel con acento cobre, esquinas de 8 px, Bricolage Grotesque en títulos y Roboto en el
  cuerpo (ADR-008, revisión del 15-nov-2026). Memoria de diseño en `.interface-design/system.md`.
- Reglas que no cambian: AA, mobile first (390 px), botones de 48 px, PWA sin red (fuentes autoalojadas, sin CDN),
  textos en es-CL, el cliente nunca ve datos internos (ADR-007), `ui.tsx` conserva su estructura.
- **Supuesto:** el aspecto final se valida con capturas en la rama antes de integrar a `main`; no hay personas reales
  disponibles para probarlo (igual que T14).

## 1. Qué tiene zed.dev (medido el 15-nov-2026)

Se abrió la página con el Chromium de Playwright a 1440 y 390 px y se leyeron los estilos calculados. Las capturas
quedaron fuera del repositorio (son material de un tercero).

| Rasgo | Cómo lo hace Zed | Medición |
|---|---|---|
| Marco tipo plano | Columna central con rieles verticales finos a los lados; marcas pequeñas en los cruces de líneas; cuadrícula muy tenue en los márgenes | Bordes de 1 px gris claro: 630 elementos |
| Tipografía en tres voces | Serif para títulos (cursiva y en color de acento en el titular); texto de cuerpo con letra de máquina de escribir; monoespaciada para metadatos y código | Serif 48 px con −0,96 px de interletra; cuerpo 12–16 px con −0,35 px |
| Esquinas casi rectas | Todo entre 2 y 4 px | 2 px: 645 elementos; 4 px: 163 |
| Botón como tecla | Primario relleno con una sombra interior abajo (borde de tecla) y una "tecla" con el atajo dentro | `inset 0 -2px 0` más oscuro + `0 1px 3px` |
| Atajos visibles | `kbd` pequeños junto a acciones (buscar, descargar) | Mono 11 px, borde de 1 px, 2 px de esquina |
| Celdas en vez de tarjetas | Secciones divididas en una grilla de celdas con líneas de 1 px, sin espacio entre ellas | — |
| Marcos punteados | Imágenes dentro de un recuadro con borde discontinuo | `1px dashed` |
| Encabezado de sección | Título serif + bajada + enlaces con chevrón a la derecha ("Ver más >") | — |
| Un acento | Gris neutro casi blanco y un solo azul saturado (titular, botón, pie) | — |
| Momento fuerte | Pie a todo el ancho en el color de acento con un patrón rayado y la marca gigante calada | — |
| Banda de aviso | Franja fina arriba ("News: …") | — |

## 2. Qué se toma, cómo se traduce y qué no

La skill `interface-design` pide que la estética salga del mundo del producto. La traducción:

| De Zed | En Cáterin | Por qué encaja en catering |
|---|---|---|
| Plano con cuadrícula | **Papel cuadriculado de la libreta de recetas** en zonas sin texto (panel del login, estados vacíos) | La ficha técnica de cocina se escribe en cuadrícula |
| Monoespaciada para metadatos | **Números de comanda**: cantidades, precios, códigos (`COT-…`), fechas y unidades en monoespaciada con cifras tabulares | Las comandas y boletas salen de impresora térmica; además alinea columnas de precios |
| Bordes discontinuos | **Línea de corte de la comanda**: separador punteado antes del total y marco punteado de la foto del producto | El ticket se corta por la línea perforada |
| Rayado diagonal | **Rayado** en el panel laurel del login, con la cloche grande calada | Sigue siendo el único momento fuerte (ADR-008) |
| Celdas con líneas | Accesos del inicio y productos del catálogo como **grilla de celdas** | Menos cajas sueltas, más orden |
| Botón tecla + atajo | Botón primario con borde de tecla; atajos solo en escritorio y como fase opcional | Feedback al presionar; la usuaria de celular no los ve |
| Serif en títulos | **IBM Plex Serif** en `h1` y títulos de sección; la frase del login en cursiva | Tono de carta de restaurante, sin perder sobriedad |
| Un acento azul | **Laurel** sigue siendo el único acento; cobre solo como detalle | Se mantiene la marca de T14 |

**No se toma:** logo, nombre, textos, el azul de Zed, sus fuentes propias (`zedMono`, la de cuerpo tipo máquina de
escribir) ni sus diagramaciones exactas o capturas del editor. Tampoco el texto chico y gris: Zed usa 10–12 px y
Cáterin usa 15 px como mínimo (`text-sm` con raíz de 17 px) por la usuaria objetivo y AA; única excepción actual: las
etiquetas de la barra inferior (`text-xs`, 12,75 px, junto a un ícono). Nada de grano de papel (imagen
extra y ruido sobre el texto).

## 3. Diseño propuesto (valores de partida)

### 3.1 Tipografía (familia IBM Plex, OFL, con `@fontsource`, solo latín, `woff2`)
| Voz | Fuente | Uso | Pesos |
|---|---|---|---|
| Títulos | IBM Plex Serif | `h1`, títulos de sección, frase del login (cursiva) | 500, 400 cursiva |
| Cuerpo | IBM Plex Sans | Todo el texto de la interfaz (reemplaza a Roboto) | variable o 400/500/600 |
| Datos | IBM Plex Mono | Cantidades, precios, códigos, fechas, `kbd`, metadatos | 400, 500 |

- Se retira Bricolage Grotesque. Interletra: `h1` −0,02 em; cuerpo normal (la mono, −0,01 em).
- Presupuesto: fuentes + íconos ≤ 200 KB en el `build` (hoy 168,6 KB). Si no cabe, se recorta en este orden: cursiva,
  Mono 500, Sans 600.

### 3.2 Forma, líneas y profundidad
- Esquinas: campos y botones 4 px; chips y `kbd` 2 px; tarjetas y celdas 6 px; cajón 8 px; tarjeta del login 8 px.
  Se logra cambiando los tokens `--radius-*` de `index.css` (las clases no cambian).
- Líneas finas: un token `--color-hairline` (borde de 1 px entre `outline-variant` y la superficie) para rieles,
  celdas y divisores; los bordes de campos siguen en `outline` (3:1, WCAG 1.4.11).
- Profundidad: bordes y cambios de superficie. Única sombra: la de los botones (tecla).
- Neutros: se mantienen casi blancos; la superficie de la página un paso más gris (`surface-container-low`) y las
  tarjetas blancas, para que las líneas finas se lean.

### 3.3 Componentes (`ui.tsx`, misma estructura)
- `Button` primario: relleno laurel, `box-shadow: inset 0 -2px 0 <laurel oscuro>, 0 1px 2px <sombra suave>`;
  al presionar baja 1 px y la sombra interior se reduce (100–160 ms, `ease-out` fuerte). Secundario: blanco, borde
  fino y la misma sombra suave. Altura mínima 48 px (Zed usa ~36 px: no se copia).
- `Kbd` nuevo: mono, borde fino, 2 px de esquina, `aria-hidden` (el atajo se anuncia con `aria-keyshortcuts`).
- `Page`: bajada opcional (`description`) y acciones como enlaces con chevrón.
- `Card`: línea fina, 6 px. Variante `Cells`: grilla de celdas con divisores de 1 px y sin espacio entre ellas.
- `Num` (o clase `font-mono tabular-nums`) para cifras.
- `Alert` y estados: sin cambios de color; esquina de 4 px.

### 3.4 Marco y fondos
- `AppShell` en escritorio (≥ 1024 px): rieles verticales finos a ambos lados del contenido y marcas en los cruces
  con la cabecera. Decorativos (`aria-hidden`), sin JavaScript. En celular, solo la línea bajo la cabecera.
- Panel del login: rayado diagonal en laurel oscuro (CSS `repeating-linear-gradient`) con la cloche grande calada.
- Cuadrícula de libreta (CSS, opacidad baja) en el panel del login y en los estados vacíos; nunca detrás de texto
  largo.
- `OfflineBanner`: franja fina con una etiqueta mono ("Sin conexión:") en vez del bloque oscuro.

### 3.5 Pantallas
| Pantalla | Cambio |
|---|---|
| Login y registro | Rayado, cuadrícula, frase en serif cursiva, botón tecla |
| Inicio de la dueña | Accesos en grilla de celdas; "Para hoy" con cifras en mono |
| Cotizar (resultado) | Tabla con cantidades y precios en mono; línea de corte punteada antes del total |
| Pedidos, Inventario, Recetas | Cifras y fechas en mono; etiquetas de estado de 2 px |
| Portal: pymes y productos | Productos en celdas; foto con marco punteado; unidad y categoría en mono |
| Portal: mis cotizaciones | Montos en mono y alineados |
| PDF de la cotización | Opcional: números en IBM Plex Mono (ReportLab necesita el TTF dentro de la API) |

### 3.6 Logo
Logotipo "Cáterin" en IBM Plex Serif 600 (hoy Bricolage), regenerado con `scripts/brand.py` y `npm run icons`. El
isotipo (cloche) no cambia; solo su esquina pasa de 116/512 a ~96/512 para acompañar las esquinas más rectas.

### 3.7 Movimiento (skill `emil-design-eng`)
- Tokens `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` y duraciones de 120/200 ms.
- Solo: presión de botones, aparición del cajón y de avisos. Nada en acciones repetidas.
- `prefers-reduced-motion`: se quitan los desplazamientos; quedan los cambios de color.
- Se reemplazan los `transition` genéricos por propiedades explícitas.

## 4. Plan por fases

Cada fase es un commit (o pocos) en la rama, con `./scripts/check.sh` en verde. Tamaños: S ≤ medio día, M 1–2 días
(estimación, no medición).

| Fase | Pasos | Archivos | Verificación | Tamaño |
|---|---|---|---|---|
| 0. Preparación | Rama, este plan, ADR-010 propuesto, skills `web-interface-guidelines` y `emil-design-eng`, T16 en el índice | `docs/`, `.claude/skills/` | Revisión del usuario | S |
| 1. Capturas "antes" | `SHOTS=antes-t16` de login, inicio, cotizar, catálogo y portal a 390 y 1280 px | `e2e/brand.e2e.ts` (ancho de escritorio), `e2e-artifacts/` | Generadas | S |
| 2. Fuentes | IBM Plex Serif/Sans/Mono en `fonts.css`, quitar Roboto y Bricolage, `--font-mono`, precaché | `package.json`, `src/fonts.css`, `index.css` | `pwa.e2e.ts` sin red; peso ≤ 200 KB | S |
| 3. Tokens | Radios, `hairline`, sombra de tecla, easing; `theme.mjs` agrega los tokens nuevos | `index.css`, `scripts/theme.mjs`, `theme.test.ts` | `theme --check`; contraste AA | S |
| 4. Componentes | `Button` tecla, `Kbd`, `Page` con bajada, `Card`/`Cells`, cifras mono | `ui.tsx`, tests de componentes | Vitest; `git diff ui.tsx` sin cambios de estructura | M |
| 5. Marco y fondos | Rieles de escritorio, rayado y cuadrícula del login, banda sin conexión | `AppShell.tsx`, `Logo.tsx`, `index.css` | axe; capturas 390 y 1280 px | M |
| 6. Pantallas | Tabla 3.5 | `pages/**` | Vitest y e2e existentes; capturas | M |
| 7. Logo | Logotipo en Plex Serif; esquina del isotipo | `scripts/brand.py`, `public/brand/`, PNG | `brand.test.tsx`; revisión visual | S |
| 8. Movimiento | Tokens, presión, cajón, `reduced-motion` | `index.css`, `ui.tsx`, `AppShell.tsx` | Revisión con `emil-design-eng`; e2e con `reducedMotion` | S |
| 9. Atajos (opcional) | `C` cotizar, `/` buscar, solo escritorio, nunca dentro de un campo, `aria-keyshortcuts` | hook nuevo, `AppShell.tsx` | Vitest de teclado; axe | S |
| 10. Revisión y cierre | `/interface-design:design-review`, `web-interface-guidelines` sobre `src/`, capturas "después", ADR-010 aceptado, `caterin-brand` y `system.md` al día, PR a `main` | docs | Barra de aprobación de la skill; check en verde | S |

Commits de ejemplo: `feat(web): tipografía IBM Plex autoalojada [T16]`, `feat(web): botón tecla y celdas [T16]`,
`feat(web): marco de plano y rayado del login [T16]`.

## 5. Criterios de aceptación
| Criterio | Cómo se verifica |
|---|---|
| Contraste AA en todos los pares, incluido el texto sobre la cuadrícula y el rayado | `theme.test.ts` y `a11y.e2e.ts` |
| Ningún texto nuevo bajo 15 px (la barra inferior sigue en 12,75 px) | Búsqueda de `text-xs` y tamaños fijos menores en `src/` |
| Funciona sin red con las fuentes nuevas | `pwa.e2e.ts` con el `build` |
| Peso de fuentes + íconos ≤ 200 KB | `du -b` de `dist/` |
| Botones de 48 px y foco visible | Vitest de `ui.tsx`; axe |
| Ninguna marca, texto, fuente propia ni color de Zed | Revisión del diff (`git grep -iw zed -- apps` vacío) |
| `reduced-motion` respetado | e2e con `reducedMotion: 'reduce'` |
| Aprobado por `/interface-design:design-review` y sin hallazgos de `web-interface-guidelines` sin justificar | Hallazgos anotados aquí |
| Capturas antes/después a 390 y 1280 px | `apps/web/e2e-artifacts/` |

## 6. Pruebas requeridas
- Vitest: contraste, marca, `Kbd`, `Button` (clases de tecla y foco), `Cells`, atajos si se hacen.
- E2E: `a11y.e2e.ts`, `pwa.e2e.ts`, `portal.e2e.ts`, `brand.e2e.ts` con el ancho de escritorio nuevo.
- API: solo si se cambia la fuente del PDF (`tests/test_quotes_api.py`).

## 7. Decisiones (el usuario aceptó todas las recomendaciones el 15-nov-2026)
| Decisión | Opciones | Recomendación |
|---|---|---|
| Fuente del cuerpo | Mantener Roboto / IBM Plex Sans | **Plex Sans**: una sola familia con la serif y la mono; similar en legibilidad |
| Logotipo | Mantener Bricolage / Plex Serif | **Plex Serif**: si no, el logo queda en una fuente que la app ya no usa |
| Atajos de teclado | Sí / no / más adelante | **Fase opcional al final**: aportan en escritorio, no en el celular |
| Fuente del PDF | Helvetica de ReportLab / Plex Mono para cifras | **Más adelante**: suma un TTF a la API |
| Cuadrícula de fondo | Solo login y vacíos / toda la app | **Solo login y vacíos**: detrás de formularios distrae |

## 8. Fuera de alcance
- Modo oscuro (Zed lo tiene; aquí sigue fuera, ADR-008).
- Cambiar la paleta laurel/cobre o la estructura de navegación.
- Animaciones decorativas, grano de papel, video o capturas de pantalla como ilustración.

## 9. Riesgos
| Riesgo | Efecto | Mitigación |
|---|---|---|
| Se ve como herramienta de programadores y no de catering | La usuaria no se identifica | Traducción al mundo de la cocina (sección 2); mono solo en cifras; serif cálida en títulos |
| Parecido excesivo con Zed | Problema de marca | Lista de lo que no se toma; revisión del diff |
| Peso de tres familias tipográficas | Primera carga lenta con mala señal | Solo latín, pocos pesos, presupuesto medido |
| Líneas finas casi invisibles en pantallas baratas | Se pierde la estructura | Las líneas son decoración; la estructura la dan el espacio y los bordes de 3:1 donde importa |
| Skills de terceros nuevas | El agente cambia de criterio | Commit fijo en `SOURCES.md`; `caterin-brand` manda |

## 10. Resultado (15-nov-2026)

Todas las fases (0 a 10) se hicieron en la rama `feat/T16-estetica-plano`, con un commit por fase o grupo de fases.

| Criterio | Resultado |
|---|---|
| Contraste AA | `theme.test.ts`: 41 pares ≥ 4,5:1 y contorno de campos ≥ 3:1. axe sin violaciones serias en login, registro, 10 pantallas de la dueña, portal y escritorio (`a11y.e2e.ts`, `plano.e2e.ts`) |
| Texto nuevo bajo 15 px | Ninguno; la barra inferior sigue en 12,75 px (excepción ya existente) |
| Sin red con las fuentes nuevas | `pwa.e2e.ts` con `vite build` + `vite preview`: Plex Sans y Serif cargan sin red |
| Peso de fuentes + marca ≤ 200 KB | **151,9 KB**: fuentes 101,6 KB (Sans variable 45,7; Serif 500 20,3; Serif cursiva 20,9; Mono 14,7) y marca e íconos 50,3 KB. Antes: 168,6 KB |
| Botones de 48 px, foco visible | `plano.test.tsx` |
| Nada de la marca de Zed | `git grep -iw zed -- apps` no encuentra nada; solo aparece en la documentación |
| Movimiento reducido | `plano.e2e.ts`: con `reducedMotion: 'reduce'` el cajón no tiene transición |
| Atajos | `plano.e2e.ts`: `C` lleva a cotizar; `/` enfoca el buscador; dentro de un campo la tecla se escribe |
| Pruebas | 144 de Vitest; e2e todos en verde salvo `vision.e2e.ts` (ya fallaba antes: el modelo de T06 está cargado, ver T15) |
| Capturas | `apps/web/e2e-artifacts/antes-t16/` y `despues-t16/`, 8 pantallas a 390 y 1280 px (carpeta ignorada por git) |

**Revisión con las skills** (`interface-design:design-review` y `web-interface-guidelines`, sobre el diff):
- Corregido: líneas de la grilla tapadas por el fondo de la celda vecina (ahora se dibujan en una capa encima); el
  inicio no usaba `Page` y quedaba sin marco; `⚠` separado del texto; la tecla visible dentro del `<label>` cambiaba el
  nombre del campo; la foto del producto y el logo de la pyme sin `width`/`height`; faltaba `touch-action:
  manipulation`; las capturas salían con "Cargando…".
- Se dejó así, con motivo: `theme-color` es el laurel de la marca y no el fondo de la página (decisión de ADR-008); los
  títulos van en mayúscula inicial del español, no *Title Case*.

**Diferencias con el plan:**
- `OfflineBanner` pasó a una franja de aviso (color de advertencia, borde fino) en vez de la etiqueta mono: el texto
  ya parte con "Sin conexión:" y una segunda fuente en la misma línea no aportaba.
- La tecla visible del atajo `C` va en el cajón de escritorio, junto a "Cotizar", y no dentro de un botón.
- Las celdas no usan `gap-px` con fondo gris (dejaba grises las celdas vacías), sino una línea por celda.
- No se agregó Plex Mono 500 (presupuesto); las cifras destacan por tamaño.
- El PDF sigue con las fuentes de ReportLab (decisión 7: más adelante).

## Resumen de cierre
Cáterin tiene ahora una estética de "plano de cocina": IBM Plex en tres voces (Serif en títulos, Sans en la interfaz,
Mono en las cifras), esquinas de 2–8 px, líneas finas como estructura, rieles con marcas en escritorio, grillas de
celdas en el inicio y el catálogo, total de la cotización como ticket con línea de corte, botón tecla, papel
cuadriculado y rayado en el login, atajos `C` y `/` en escritorio y un cajón que entra suave (y quieto si se pide
reducir movimiento). Pesa menos que antes (151,9 KB contra 168,6 KB). Pendiente: que el usuario revise las capturas
y apruebe la integración a `main`, y mostrarlo a personas reales.
