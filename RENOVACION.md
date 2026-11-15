# Renovación de Cáterin: nueva identidad visual y catálogo para clientes

- Estado: **propuesta** (15-nov-2026, pedido del usuario; revisada contra el código el mismo día, ver sección 10)
- Depende de: T13 (portal de clientes, ADR-007), T08 (frontend PWA)
- Al aprobarla: crear **T14 (identidad visual)** y **T15 (catálogo)**, los **ADR-008 (identidad visual)** y
  **ADR-009 (catálogo del portal)**, y registrarlos en `docs/tasks/00-INDEX.md`. La numeración sigue el orden de
  trabajo: la identidad va primero (sección 5).

## 1. Qué se pide

1. **Catálogo de productos de las pymes para la vista del cliente:** el cliente selecciona una pyme de Cáterin y ve sus
   productos.
2. **Mejor diseño con logos:** hoy la app usa Material Design y se mantiene así, pero tiene que transmitir que es un
   software de catering. Para eso se usan skills de diseño para el agente (sección 4.4).

## 2. Punto de partida (verificado en el código)

**Portal del cliente hoy**

- El cliente elige la pyme con un `<select>` dentro de la pantalla de cotizar (`NewQuote.tsx`, modo portal). Los
  productos solo se cargan para llenar las listas de esa pantalla (`GET /portal/products?pyme_id=`).
- No existe una pantalla para **mirar** pymes ni productos antes de cotizar. El inicio del cliente (`PortalHome.tsx`)
  solo muestra "Nueva cotización" y sus cotizaciones guardadas.
- Rutas del cliente: inicio, `#/cotizar` y `#/solicitudes/:id` (`CustomerRoutes` en `App.tsx`). La navegación del
  cliente en `AppShell.tsx` tiene dos destinos: "Mis cotizaciones" (`/`) y "Nueva cotización" (`/cotizar`).
- API existente:
  - `GET /portal/directory` (público): pymes con el portal abierto (`customer_code` no nulo), con nombre y comuna.
  - `GET /portal/pymes` (cliente con sesión): las anteriores **más** las pymes donde el cliente ya tiene cuenta, aunque
    hayan cerrado el portal; marca `joined`. Es la fuente correcta para el catálogo.
  - `GET /portal/products?pyme_id=` (cliente con sesión): recetas activas con `is_final_product`.
- El acceso a pymes cerradas **ya está protegido**: `_pyme_for` en `portal/service.py` responde 404
  `pyme_not_available` si la pyme tiene el portal cerrado y el cliente no tiene cuenta ahí, y lo cubre
  `test_cannot_quote_to_a_pyme_with_closed_portal` en `tests/test_portal.py`.
- `ProductOut` solo trae `id`, `name` y `yield_unit`: no hay foto, descripción ni categoría. `PortalPymeOut` trae `id`,
  `name`, `commune` y `joined`.
- `NewQuote` ya lee `?pyme=` de la ruta (`matchPath` ignora la parte `?…`), pero solo al montarse.
- Offline: el portal **no usa** `useCached`; todas sus pantallas piden a la red con `api()`. El caché de
  `offline/cache.ts` se guarda por pyme de la sesión (`setScope`).
- Pruebas: no hay e2e de navegador del portal (pendiente de T13) y `a11y.e2e.ts` no revisa pantallas del cliente.
- ADR-007: el cliente nunca ve costos, margen, insumos, proveedores ni stock. Los precios solo aparecen en la
  cotización; si falta un precio de insumo, se muestra "precio por confirmar".

**Diseño hoy**

- `index.css` define Material Design 3 con un esquema **neutro gris** (`--color-primary: #3d4449`) y roles MD3
  (`primary`, `surface-container`, `on-surface-variant`…). `ui.tsx` usa esos roles, así que cada componente depende del
  rol y no de un color fijo. El contraste AA de esos pares se "verificó a mano" (comentario de `index.css`): no hay una
  prueba automática.
- **Roboto no está incluida.** `--font-sans` la nombra primero, pero no hay `@font-face` ni paquete de fuentes: se ve
  Roboto solo si el teléfono la tiene instalada (Android sí; iPhone y Windows caen a la fuente del sistema).
- El logo es `public/icon.svg`: un cuadrado gris redondeado con una cloche (cúpula de servir). Es la base correcta, pero
  no se usa en ninguna pantalla: el login, la barra superior y el cajón muestran solo el texto `t.appName`.
- El manifiesto PWA (`vite.config.ts`) declara solo ese SVG, con `purpose: 'any maskable'`. Como ícono *maskable* no
  sirve: tiene esquinas redondeadas y la bandeja de la cloche sale de la zona segura (círculo del 80 % central), así
  que Android la recorta. No hay PNG ni `apple-touch-icon` (iPhone no usa SVG para la pantalla de inicio).
- `theme-color` es `#3d4449` en dos lugares: `index.html` y el manifiesto.
- El PDF de la cotización (`quotes/pdf.py`, ReportLab) lleva como título el nombre de la pyme. ReportLab no dibuja SVG
  sin una dependencia extra (`svglib`), así que cualquier logo en el PDF debe ir en PNG y vivir dentro de la API.
- Resultado: la app se ve como un panel de administración gris, sin pistas de que trata de comida y eventos.

## 3. Parte 1: catálogo de pymes y productos (vista del cliente)

### 3.1 Flujo

```
Inicio del cliente → Pymes → (elige una pyme) → Productos de la pyme → Cotizar con esta pyme → pantalla de cotizar
```

Máximo 3 clics desde el inicio hasta empezar a cotizar (criterio de AGENTS.md): "Pymes" (barra de navegación o acceso
del inicio), la tarjeta de la pyme y "Cotizar con esta pyme". Marcar productos es opcional: cada producto marcado suma
un toque, pero ahorra elegirlo después en la lista de cotizar.

### 3.2 Pantallas

| Pantalla | Ruta propuesta | Contenido |
|---|---|---|
| Elegir pyme | `#/pymes` | Datos de `GET /portal/pymes`. Tarjetas con logo (o círculo con la inicial), nombre y comuna. Etiqueta `t.portal.joined` ("ya le cotizaste") si `joined`. Buscador por nombre o comuna, en el navegador (la lista es corta). Estado vacío con `t.portal.noPymes`. |
| Productos de la pyme | `#/pymes/:id` | Encabezado con logo, nombre y comuna. Cuadrícula de productos: nombre, unidad de venta y foto opcional (marcador con ícono si no hay). Cada tarjeta se marca con "Agregar a mi cotización" (botón de alternar, `aria-pressed`). Una barra inferior fija muestra "Cotizar con esta pyme" y, si hay productos marcados, "Cotizar N productos". Si la pyme no tiene productos, lo dice y deja cotizar igual (texto libre). |
| Cotizar | `#/cotizar?pyme=<id>&p=<id1>,<id2>` | La pantalla actual. Con `p`, abre directo en el formulario manual con una línea por producto marcado (producto elegido, cantidad vacía). Los ids que no sean de esa pyme se descartan sin error; la API vuelve a validar (422 `product_not_found`). |

Se elige pasar los productos **por la ruta** y no por un estado compartido: sobrevive a recargar la página, funciona
sin red y no agrega un *store* nuevo.

Cambios en la navegación: un destino "Pymes" en la navegación del cliente (`AppShell.tsx`, ícono de tienda) y un
acceso en `PortalHome.tsx` junto a "Nueva cotización".

### 3.3 Qué se muestra y qué no

- **Sin precios en la primera versión.** Es coherente con ADR-007 y con el riesgo abierto de T13 ("validar con una
  emprendedora real si quiere publicar sus precios en línea"). El cliente ve el precio al cotizar.
- Nunca se muestran costos, margen, insumos, proveedores ni stock.
- Solo aparecen los productos que hoy ya ve el cliente: recetas activas marcadas como producto final.
- Una pyme con el portal cerrado no aparece, salvo para el cliente que ya tiene cuenta en ella (regla actual de
  `_pyme_for`, se mantiene).

### 3.4 Datos y API

**Versión mínima (sin migraciones, recomendada para empezar):**
- `GET /portal/pymes` para la lista y `GET /portal/products?pyme_id=` para los productos. No cambia la API.
- Se agrega una prueba de lista blanca: las claves de `ProductOut` y `PortalPymeOut` son exactamente las permitidas, así
  un campo nuevo con datos internos rompe la prueba.

**Versión completa (con migración reversible, después de validar la mínima con una pyme real):**
- `pyme`: `logo_path` y `description` (hasta 280 caracteres) opcionales; se agregan a `PortalPymeOut` como `logo_url` y
  `description`. Ojo: `PortalPymeOut` también sale en rutas **públicas** (`/portal/directory`, `/portal/pymes/{code}`),
  así que la pyme debe saber que su logo y descripción quedan visibles para cualquiera.
- Receta (producto del catálogo): `catalog_description`, `photo_path`, `category` y `visible_in_catalog` (por defecto
  `true`, para no cambiar lo que ya ve el cliente); se agregan a `ProductOut` como `description`, `photo_url` y
  `category`.
- `visible_in_catalog = false` saca el producto de **todo** el portal (catálogo, extractor y solicitudes), porque
  `product_choices` y `create_request` usan la misma función `products()`. Así la regla es una sola.
- Subida de imágenes (solo la dueña): JPEG, PNG o WebP de hasta 2 MB; se re-codifican con Pillow (ya es dependencia) a
  WebP de 512 px (logo) u 800 px (foto), lo que además **borra los metadatos EXIF** (pueden traer la ubicación GPS).
  Se guardan en `settings.storage_dir` (`/data`, ya usado por la API), en una carpeta por pyme.
- Cómo se sirven: la API usa token *Bearer* en la cabecera, y un `<img src>` no lo envía. Propuesta: servirlas sin
  sesión con una URL que incluye el hash del contenido (`/portal/media/<pyme_id>/<sha256>.webp`), solo para pymes con
  portal abierto o productos visibles, con `Cache-Control: public, max-age=31536000, immutable`. Alternativa: pedirlas
  con `fetch` y mostrarlas como `blob:` (más código y sin caché del navegador). Se decide en ADR-009.

### 3.5 Tareas (T15)

- [ ] ADR-009: catálogo del portal (qué se muestra, precios fuera, qué productos se publican, cómo se sirven las imágenes).
- [ ] API (mínima): prueba de lista blanca de esquemas.
- [ ] API (completa): migración, campos nuevos, subida y entrega de imágenes, filtro `visible_in_catalog`.
- [ ] Web: `PortalPymes.tsx` y `PortalPyme.tsx`; rutas en `CustomerRoutes`; destino en la navegación; textos en
      `i18n.ts` (es-CL).
- [ ] Web: `NewQuote` recibe los productos elegidos (`&p=`).
- [ ] Web (completa): logo y descripción en `Settings.tsx`; foto, descripción, categoría y "mostrar en el catálogo" en
      `RecipeDetail.tsx`.
- [ ] Offline: cachear la lista de pymes y los productos con `useCached` y documentar en ADR-004 qué funciona sin red.
- [ ] Docs: `API.md`, OpenAPI (sale de FastAPI), `docs/DATA_MODEL.md` (si hay migración) y la sección del portal en la
      guía de usuario de T12 (la guía todavía no existe).

### 3.6 Criterios de aceptación y pruebas

- El cliente llega de su inicio a la cotización de una pyme en 3 clics (lo comprueba el e2e).
- Ninguna respuesta del catálogo contiene costos, margen, insumos, proveedores ni stock (prueba de lista blanca en
  `apps/api/tests/test_portal.py`).
- Un cliente sin cuenta en una pyme con el portal cerrado no ve sus productos (404 `pyme_not_available`). Ya cubierto;
  se mantiene como prueba de regresión.
- Versión completa: la dueña de una pyme no puede cambiar la foto de una receta de otra pyme; un archivo de más de 2 MB
  responde 413; la imagen guardada no tiene EXIF.
- Web: pruebas en `Portal.test.tsx` (listar pymes, buscar, abrir una, marcar productos, pasar a cotizar con las líneas
  prellenadas) y un e2e nuevo `apps/web/e2e/portal.e2e.ts` (el primero del portal con navegador).
- Accesibilidad AA en las pantallas nuevas: `a11y.e2e.ts` suma una prueba con sesión de cliente. Capturas a 390 px en
  `apps/web/e2e-artifacts/` (`pymes-390.png`, `pyme-productos-390.png`).

## 4. Parte 2: nuevo diseño con identidad de catering

### 4.1 Principio

Seguir con Material Design 3 y no tocar la estructura ni los componentes. Lo que cambia son los **tokens** (color,
tipografía), el **logo**, los **íconos**, la **imagen** y el tono de los textos. Como `index.css` ya usa roles MD3, el
cambio principal es reemplazar los valores del bloque `@theme`.

### 4.2 Dirección visual (propuesta a validar)

La idea es pasar de "panel gris" a "mesa bien servida": cálido, apetitoso y ordenado.

- **Color:** reemplazar el gris por una paleta cálida generada desde un color semilla. Propuesta de partida: terracota
  o ají (primario), oliva o hierbas (secundario) y neutros crema. Los valores se generan con
  `@material/material-color-utilities` (Apache-2.0) desde un script versionado en el repositorio
  (`apps/web/scripts/theme.mjs`), para que cambiar la semilla sea repetible. No se escriben a mano.
- Mantener los nombres de rol de `index.css`. Los estados `warning`, `success` e `info` se armonizan con la semilla
  (`Blend.harmonize` de la misma librería) para que no desentonen.
- **Contraste:** reemplazar el "verificado a mano" por una prueba de Vitest que lee `index.css` y calcula el contraste
  de cada par `on-X` / `X` (mínimo 4.5:1 para texto normal).
- **Tipografía:** Roboto para el cuerpo (MD3), ahora **incluida** en la app. Una tipografía de display para títulos y
  para el logotipo, a elegir entre fuentes con licencia OFL. Todas autoalojadas con paquetes `@fontsource/*` (versión
  fija), solo el subconjunto latino y en `woff2`: la PWA debe funcionar sin red, así que no se usa CDN.
- **Íconos:** ampliar `Icon.tsx` con íconos de comida (cloche, cubiertos, bandeja) y de tienda, tomados de Material
  Symbols (Apache-2.0, mismo estilo y `viewBox` 24 que los actuales). Anotarlos en `THIRD_PARTY_NOTICES.md`.
- **Imagen:** foto por producto en el catálogo (versión completa); si no hay, un marcador con el ícono de cloche.
- **Textos:** más cálidos, siempre en es-CL y en lenguaje simple (ya es regla del proyecto).

### 4.3 Logo

Se parte de la cloche de `icon.svg`, que ya comunica catering.

| Entregable | Uso |
|---|---|
| Isotipo (cloche) | Ícono de la app, favicon, avatar |
| Logotipo "Cáterin" (isotipo + palabra, texto convertido a trazos) | Login, cabecera de la app, presentaciones |
| Versión horizontal y apilada | Cabecera (horizontal) y login o bienvenida (apilada) |
| Versión monocromo | PDF en blanco y negro, fondos de color |
| Íconos PWA PNG 192 y 512 (`any`), 512 *maskable* aparte y `apple-touch-icon` 180 | Hoy el manifiesto solo tiene el SVG y lo marca como *maskable* sin serlo |
| PNG del isotipo para el PDF | `apps/api/app/assets/`, porque el PDF se arma en la API |

Los PNG se generan desde el SVG con `@vite-pwa/assets-generator` (MIT, complemento de `vite-plugin-pwa`) y se guardan en
el repositorio, para no depender de la herramienta al compilar.

Dónde se usa: login (hoy solo texto), cabecera y cajón de `AppShell`, registro de cliente, inicio del cliente,
`theme-color` (en `index.html` **y** en el manifiesto), README y portada de la documentación.

**PDF de la cotización:** el PDF es de la pyme para su cliente, así que el logo de Cáterin **no** reemplaza el nombre
de la pyme. Arriba va el logo de la pyme (cuando exista, versión completa del catálogo) y su nombre; abajo, una línea
pequeña "Hecha con Cáterin" con el isotipo monocromo.

**Logo de cada pyme:** campo opcional que se muestra en las tarjetas del catálogo y en el PDF. Si no hay, un círculo
con la inicial. Dónde se guarda: ver 3.4 y la sección 6.

### 4.4 Skills de diseño (buscadas en la web)

Ninguna estaba instalada en las skills de la cuenta, así que se proponen dos skills abiertas que se complementan.
El README de `material-3` dice que, si ambas están activas, MD3 aporta el sistema de diseño y `frontend-design` la
dirección creativa dentro de esas restricciones.

| Skill | Para qué | Licencia |
|---|---|---|
| `material-3` ([hamen/material-3-skill](https://github.com/hamen/material-3-skill)) | Tokens, temas con colores de marca, modo oscuro, tipografía, forma y auditoría de cumplimiento MD3 (`/material-3 audit`) | MIT |
| `frontend-design` ([anthropics/skills](https://github.com/anthropics/skills)) | Alejar la interfaz de los valores por defecto hacia una identidad propia del tema (catering) | Apache-2.0 |

Instalación, desde la raíz del repositorio (se instalan en `.claude/skills/`):

```bash
npx skills add hamen/material-3-skill --skill material-3 --agent claude-code
npx skills add anthropics/skills --skill frontend-design --agent claude-code
```

Para otro agente, el mismo comando eligiendo el agente en el instalador.

Notas:
- Revisar el `SKILL.md` de cada una antes de instalar, como con cualquier dependencia, y confirmar los nombres de las
  opciones (`--skill`, `--agent`) con `npx skills --help`: el instalador es una herramienta de terceros.
- Fijar la versión: anotar en el ADR-008 el commit de cada repositorio instalado. Las skills son instrucciones para el
  agente; una actualización sin revisar cambia su comportamiento.
- `material-3` está pensada sobre todo para Jetpack Compose y cubre la web de forma secundaria. Aquí sirve para
  tokens, tema y auditoría. El código sigue siendo React + Tailwind v4.
- Después de decidir la marca, crear una skill del proyecto, `.claude/skills/caterin-brand/SKILL.md`, corta, con la
  semilla de color, las tipografías, las reglas del logo y los textos de ejemplo, para que cualquier agente respete la
  misma identidad.

### 4.5 Tareas (T14)

- [ ] Decidir color semilla, tipografía de display y dirección del logo (sección 6).
- [ ] ADR-008: identidad visual sobre MD3 (qué cambia y qué no, skills y su versión).
- [ ] Tokens: script de tema, nuevo `@theme` en `index.css`, prueba de contraste y fuentes autoalojadas.
- [ ] Logo: isotipo, logotipo, versiones y favicon en `public/brand/`; PNG, *maskable* y `apple-touch-icon`; actualizar
      manifiesto, `theme-color` e `index.html`; precachear fuentes e íconos.
- [ ] Componente `Logo.tsx` y su uso en login, `AppShell`, registro e inicio del cliente.
- [ ] PDF: pie "Hecha con Cáterin" con el isotipo PNG.
- [ ] Íconos de comida y tienda en `Icon.tsx`.
- [ ] Auditoría con `material-3` y revisión de dirección con `frontend-design`.
- [ ] Capturas a 390 px antes y después (`apps/web/e2e-artifacts/`).
- [ ] Skill del proyecto `caterin-brand`.

### 4.6 Criterios de aceptación

- Siguen usándose los roles y componentes MD3 de `ui.tsx`: el cambio visual sale de los tokens y los activos
  (`git diff` de `ui.tsx` sin cambios de estructura).
- Contraste AA: la prueba de contraste pasa y `a11y.e2e.ts` no reporta violaciones.
- La PWA sigue instalable y funciona offline con las fuentes y los logos incluidos (`pwa.e2e.ts` comprueba que el
  manifiesto tiene PNG `any` y `maskable` y que las fuentes están en el precaché).
- El peso agregado por fuentes e íconos no pasa de 200 KB (propuesta; se mide en el `build`).
- El logo aparece en login, cabecera, registro e inicio del cliente, y el isotipo en el pie del PDF.
- Prueba de 5 segundos con al menos 5 personas que no conocen la app: ven el login 5 segundos y se les pregunta de qué
  trata. Meta: la mayoría menciona comida, catering o eventos. Se reporta el resultado tal cual (AGENTS.md, sección 10).

## 5. Orden de trabajo sugerido

1. Decisiones de la sección 6.
2. T14: tokens, fuentes y logo (4.5). Va primero para no estilizar dos veces las pantallas nuevas.
3. T15: catálogo (3.5), versión mínima, ya con la nueva identidad.
4. Validar con una pyme real; recién ahí, la versión completa del catálogo.
5. Auditoría, capturas y cierre de las tareas en `00-INDEX.md`.

## 6. Decisiones abiertas (con recomendación)

| Decisión | Opciones | Recomendación |
|---|---|---|
| Precios en el catálogo | Sin precios / "desde $X" que cada pyme activa | Sin precios en v1 (ADR-007). Revisar después de hablar con una pyme |
| Versión del catálogo | Mínima / completa | Mínima primero; la completa solo si la pyme real pide fotos |
| Dónde se guardan fotos y logos | Disco del servidor / almacenamiento de objetos / solo URL externa | Disco del servidor en `storage_dir`, que ya existe y entra en los respaldos de T11. "Solo URL" se descarta: no funciona offline y cada visita le avisa a un tercero quién mira |
| Cómo se sirven las imágenes | URL pública con hash / `fetch` con sesión | URL pública con hash, solo de pymes con portal abierto (3.4) |
| Qué productos se publican | Todas las recetas finales activas / `visible_in_catalog` | Todas en v1; `visible_in_catalog` en la versión completa |
| Color semilla y logotipo | Terracota, ají, oliva… | Validar con la dueña de una pyme real antes de fijarlos |
| Modo oscuro | Sí / no | Fuera de este alcance; el script de tema deja listo el esquema oscuro para después |

## 7. Fuera de alcance

- Pagos, abonos, carrito con compra directa o firma de la cotización (ya fuera en T13).
- Reseñas, favoritos o recomendaciones.
- Cambiar de Material Design a otro sistema de diseño.
- Modo oscuro.

## 8. Archivos que se tocarían

- Web: `apps/web/src/index.css`, `index.html`, `vite.config.ts` (manifiesto y precaché), `package.json` (fuentes,
  `material-color-utilities`, generador de íconos), `scripts/theme.mjs`, `public/`, `components/AppShell.tsx`,
  `components/Icon.tsx`, `components/Logo.tsx` (nuevo), `pages/Login.tsx`, `pages/portal/CustomerRegister.tsx`,
  `pages/portal/PortalHome.tsx`, `pages/portal/PortalPymes.tsx` y `PortalPyme.tsx` (nuevas), `pages/NewQuote.tsx`,
  `App.tsx`, `api.ts`, `i18n.ts`; en la versión completa también `pages/Settings.tsx` y `pages/RecipeDetail.tsx`.
  `components/ui.tsx` no debería cambiar.
- Pruebas web: `pages/portal/Portal.test.tsx`, prueba de contraste nueva, `e2e/portal.e2e.ts` (nuevo),
  `e2e/a11y.e2e.ts`, `e2e/pwa.e2e.ts`.
- API: `modules/quotes/pdf.py`, `app/assets/` (nuevo), `tests/test_portal.py`; en la versión completa también
  `modules/portal/{router,schemas,service}.py`, los módulos de pyme y recetas (subida de imágenes), `db/models.py` y la
  migración.
- Docs: ADR-008, ADR-009, T14, T15, `API.md`, `DATA_MODEL.md`, ADR-004 (tabla offline), `THIRD_PARTY_NOTICES.md`,
  README, `00-INDEX.md`.

## 9. Plan detallado de desarrollo

Cada fase termina con la Definición de Hecho de AGENTS.md (sección 8): tipos, lint y pruebas en verde, documentación al
día y comandos verificados. Una tarea a la vez, cada una en su rama y con commits pequeños que llevan el ID. Los
tamaños son relativos (S: medio día o menos, M: uno o dos días, L: más de dos días) y son una **estimación**, no una
medición.

### Fase 0. Decisiones y documentos (sin código de producto)

| # | Paso | Resultado | Tamaño |
|---|---|---|---|
| 0.1 | Responder las decisiones de la sección 6 con el usuario | Decisiones anotadas en este documento | S |
| 0.2 | Crear `T14-identidad-visual.md` y `T15-catalogo-portal.md` con la plantilla de AGENTS.md (7.3) y registrarlas en `00-INDEX.md` como pendientes | Tareas visibles en el índice | S |
| 0.3 | Revisar el `SKILL.md` de `material-3` y `frontend-design`, instalarlas y anotar el commit de cada una | `.claude/skills/` con ambas | S |
| 0.4 | Redactar ADR-008 en estado "propuesto" | ADR listo para aceptar al cerrar T14 | S |

Salida: decisiones cerradas o con supuesto explícito en el documento de la tarea (AGENTS.md, 6.6).

### Fase 1. T14 identidad visual (rama `feat/T14-identidad-visual`)

| # | Paso | Archivos | Verificación | Tamaño |
|---|---|---|---|---|
| 1.1 | Capturas "antes" a 390 px de login, inicio de la dueña, cotizar, inicio del cliente y PDF | `apps/web/e2e-artifacts/antes/` | Generadas con los e2e actuales | S |
| 1.2 | Script de tema desde la semilla: escribe los roles MD3 y los estados armonizados | `scripts/theme.mjs`, `index.css` | `npm run theme` produce el mismo `@theme` dos veces seguidas | S |
| 1.3 | Prueba de contraste de cada par `on-X` / `X` | `src/theme.test.ts` | Falla si un par baja de 4.5:1 | S |
| 1.4 | Fuentes autoalojadas: Roboto 400/500 y la de display, subconjunto latino, `font-display: swap`; agregar `woff2`, `png` y `svg` a `workbox.globPatterns` (hoy el precaché por defecto solo toma js, css y html) | `package.json`, `main.tsx`, `index.css`, `vite.config.ts` | `pwa.e2e.ts`: con la red cortada el texto usa la fuente; peso medido en el `build` | M |
| 1.5 | Logo: isotipo, logotipo horizontal y apilado, monocromo, con el texto en trazos | `public/brand/*.svg` | Revisión visual y del usuario | M |
| 1.6 | Íconos PWA: PNG 192/512 `any`, 512 `maskable` con fondo completo y la cloche dentro de la zona segura, `apple-touch-icon` 180, favicon | `public/`, `vite.config.ts`, `index.html` | `pwa.e2e.ts` lee el manifiesto; Lighthouse "instalable" | S |
| 1.7 | `theme-color` nuevo en `index.html` y en el manifiesto | `index.html`, `vite.config.ts` | Igual en ambos (prueba simple) | S |
| 1.8 | Componente `Logo` (variantes `isotipo`, `horizontal`, `apilado`; nombre accesible "Cáterin") y uso en login, barra superior, cajón, registro e inicio del cliente | `components/Logo.tsx`, `Login.tsx`, `AppShell.tsx`, `CustomerRegister.tsx`, `PortalHome.tsx` | Vitest: el login muestra el logo con su nombre accesible | S |
| 1.9 | Íconos de cloche, cubiertos, bandeja y tienda | `components/Icon.tsx`, `THIRD_PARTY_NOTICES.md` | Se ven en la galería de capturas | S |
| 1.10 | PDF: pie "Hecha con Cáterin" con el isotipo PNG | `modules/quotes/pdf.py`, `app/assets/caterin-isotipo.png` | La prueba de PDF existente sigue pasando y el texto del pie aparece (`pypdf`) | S |
| 1.11 | Revisión de textos de bienvenida y estados vacíos con tono más cálido | `i18n.ts` | Revisión del usuario; sin cambiar textos que usan las pruebas sin actualizarlas | S |
| 1.12 | Auditoría con `/material-3 audit` y revisión con `frontend-design`; corregir lo que salga | según hallazgos | Hallazgos y respuesta anotados en T14 | M |
| 1.13 | Capturas "después", `a11y.e2e.ts`, prueba de 5 segundos (4.6) | `e2e-artifacts/`, T14 | Sin violaciones; resultado de la prueba anotado tal cual | S |
| 1.14 | Skill `caterin-brand`, ADR-008 aceptado, README con logo, resumen de cierre de T14 | `.claude/skills/caterin-brand/SKILL.md`, docs | T14 "hecha" en `00-INDEX.md` | S |

Commits de ejemplo: `feat(web): tema MD3 cálido generado desde la semilla [T14]`,
`feat(web): fuentes autoalojadas en el precaché [T14]`, `feat(web): logo e íconos PWA maskable [T14]`.

### Fase 2. T15 catálogo, versión mínima (rama `feat/T15-catalogo-portal`)

| # | Paso | Archivos | Verificación | Tamaño |
|---|---|---|---|---|
| 2.1 | Prueba de lista blanca de `ProductOut` y `PortalPymeOut` | `tests/test_portal.py` | Falla si aparece un campo no permitido | S |
| 2.2 | Textos nuevos (título "Pymes", buscador, "Agregar a mi cotización", "Cotizar con esta pyme", "Cotizar N productos", sin productos, sin resultados) | `i18n.ts` | Sin textos sueltos en los componentes | S |
| 2.3 | `PortalPymes.tsx`: lista con `useCached('portal:pymes', '/portal/pymes')`, buscador, tarjetas con inicial, `joined`, estado vacío, aviso "datos guardados el…" sin red | `pages/portal/PortalPymes.tsx` | Vitest: lista, busca y muestra el vacío | M |
| 2.4 | `PortalPyme.tsx`: encabezado, cuadrícula con `useCached('portal:products:<id>', …)`, marcar productos, barra inferior, 404 con mensaje claro y vuelta a la lista | `pages/portal/PortalPyme.tsx` | Vitest: marca dos productos y navega a `/cotizar?pyme=…&p=…` | M |
| 2.5 | Rutas `/pymes` y `/pymes/:id` en `CustomerRoutes`; destino "Pymes" en la navegación; acceso en `PortalHome` | `App.tsx`, `AppShell.tsx`, `PortalHome.tsx` | Vitest: el destino aparece solo para clientes | S |
| 2.6 | `NewQuote`: leer `p` y abrir en modo manual con las líneas prellenadas; descartar ids ajenos | `pages/NewQuote.tsx` | Vitest: llega con dos líneas, cantidad vacía, y guarda | S |
| 2.7 | e2e del portal: registro con el enlace de demo, catálogo, marcar, cotizar y guardar; conteo de clics | `e2e/portal.e2e.ts` | Pasa en CI; cierra también el pendiente de e2e de T13 | M |
| 2.8 | Accesibilidad y capturas con sesión de cliente | `e2e/a11y.e2e.ts`, `e2e-artifacts/` | Sin violaciones AA | S |
| 2.9 | Docs: ADR-009, ADR-004 (lista de pymes y productos sin red; cotizar sigue necesitando red), `API.md`, resumen parcial de T15 | docs | Revisión | S |

Commits de ejemplo: `feat(web): catálogo de pymes y productos para el cliente [T15]`,
`feat(web): cotizar con los productos elegidos en el catálogo [T15]`, `test(web): e2e del portal de clientes [T15]`.

### Fase 3. Validación con una pyme real (sin código)

- Mostrar el catálogo mínimo y la nueva identidad a la dueña de una pyme real (y, si se puede, a uno de sus clientes).
- Preguntas: ¿quiere fotos y descripciones?, ¿quiere publicar precios "desde"?, ¿hay recetas que no quiere mostrar?,
  ¿reconoce la marca como algo de catering?
- Anotar las respuestas en T15. Si no pide fotos ni ocultar productos, la Fase 4 queda en `ROADMAP.md`.

### Fase 4. T15 catálogo, versión completa (opcional, misma tarea o T15b)

| # | Paso | Archivos | Verificación | Tamaño |
|---|---|---|---|---|
| 4.1 | Migración reversible: campos de pyme y receta (3.4), `visible_in_catalog` con valor por defecto `true` | `db/models.py`, `alembic/versions/` | `alembic upgrade head` y `downgrade -1` desde cero | S |
| 4.2 | Servicio de imágenes: validación de tipo y tamaño, re-codificación a WebP sin EXIF, guardado por pyme en `storage_dir`, nombre por hash | módulo nuevo en la API | Pruebas: 413, tipo inválido 415, EXIF borrado | M |
| 4.3 | Rutas de la dueña para subir y borrar logo y foto (solo rol dueña, filtradas por `pyme_id` desde la dependencia central) | routers de pyme y recetas | Prueba multi-tenant: la pyme A no toca recetas de la B; la colaboradora recibe 403 | M |
| 4.4 | Entrega pública por hash con `Cache-Control` inmutable, solo de pymes con portal abierto o con clientes | `modules/portal/router.py` | Prueba: pyme cerrada sin clientes responde 404 | S |
| 4.5 | `PortalPymeOut` y `ProductOut` con los campos nuevos; filtro `visible_in_catalog` en `products()`; actualizar la lista blanca | `modules/portal/` | Las pruebas de lista blanca y de extractor siguen en verde | S |
| 4.6 | Web de la dueña: logo y descripción en Ajustes; foto, descripción, categoría y "mostrar en el catálogo" en la receta | `Settings.tsx`, `RecipeDetail.tsx` | Vitest y e2e de ajustes | M |
| 4.7 | Web del cliente: logo y fotos en las tarjetas, categoría como filtro si hay más de una; caché de imágenes con `runtimeCaching` *CacheFirst* (máx. 100 imágenes, 30 días) | `PortalPymes.tsx`, `PortalPyme.tsx`, `vite.config.ts` | `pwa.e2e.ts`: la imagen ya vista se muestra sin red | M |
| 4.8 | PDF con el logo de la pyme si existe | `modules/quotes/pdf.py` | Prueba de PDF con y sin logo | S |
| 4.9 | Respaldos: la carpeta de imágenes entra en el respaldo de T11 | `T11-despliegue.md`, scripts de respaldo | Restaurar un respaldo de prueba muestra las imágenes | S |
| 4.10 | Docs: `DATA_MODEL.md`, `API.md`, `SECURITY.md` (imágenes públicas, EXIF), cierre de T15 | docs | T15 "hecha" en `00-INDEX.md` | S |

### Fase 5. Cierre

- Auditoría final con `material-3` de las pantallas nuevas del catálogo.
- Capturas finales a 390 px y comparación antes/después en el resumen de T14.
- `00-INDEX.md` al día, resúmenes de cierre de T14 y T15 con lo hecho, lo pendiente y los riesgos.
- Mover este documento a `docs/` (por ejemplo `docs/RENOVACION.md`) o reemplazarlo por los documentos de T14 y T15.

### Riesgos del plan

| Riesgo | Efecto | Mitigación |
|---|---|---|
| La semilla o el logo no gustan a la pyme real | Rehacer tokens y activos | El script de tema hace barato cambiar la semilla; validar el logo en Fase 0 con bocetos |
| Las fuentes pesan mucho en un celular con mala señal | Primera carga lenta | Subconjunto latino, solo dos pesos, presupuesto de 200 KB medido |
| Un campo nuevo filtra datos internos al cliente | Rompe ADR-007 | Prueba de lista blanca de esquemas (2.1) |
| Imágenes públicas por URL | Cualquiera con el enlace ve el logo o la foto | Solo pymes con portal abierto, nombres por hash, la pyme lo acepta al subir, anotado en `SECURITY.md` |
| Fotos de celular con ubicación | Exponen dónde vive o trabaja la dueña | Re-codificar siempre y borrar EXIF (4.2) |
| Las skills de terceros cambian | El agente se comporta distinto | Commit fijo anotado en ADR-008 y revisión del `SKILL.md` |

## 10. Revisión del 15-nov-2026: qué se corrigió

- **Numeración:** T14 pasa a ser la identidad visual y T15 el catálogo (igual con ADR-008 y ADR-009), para que coincida
  con el orden de trabajo. En `docs/adr/` hay dos archivos ADR-006 (`rag-sobre-datos-del-negocio` y `rls-postgres`); el
  próximo número libre sigue siendo ADR-008, pero conviene corregir el duplicado aparte.
- **Seguridad del catálogo:** la verificación de que `/portal/products` rechaza pymes cerradas ya está hecha y probada;
  se cambió de tarea a punto de partida. Se aclaró la regla para clientes que ya tienen cuenta en una pyme cerrada.
- **Fuente de la lista de pymes:** `GET /portal/pymes` (con sesión, trae `joined`), no `/portal/directory`.
- **Etiqueta "Ya cotizaste aquí":** se usa el texto existente `t.portal.joined`.
- **Roboto:** no está incluida hoy; el documento decía que sí.
- **Ícono maskable:** el SVG actual se declara *maskable* sin cumplir la zona segura; se agregó el `apple-touch-icon`.
- **Precaché:** `workbox.globPatterns` por defecto no incluye `woff2` ni `png`; sin cambiarlo, las fuentes no
  funcionan offline.
- **PDF:** ReportLab necesita PNG y el activo debe estar en la API; el logo de Cáterin va al pie, no reemplaza a la pyme.
- **Imágenes:** un `<img>` no envía el token *Bearer*; se agregó cómo servirlas, el borrado de EXIF y el respaldo.
- **`visible_in_catalog`:** afecta también al extractor y a las solicitudes, porque comparten `products()`.
- **Paso de productos a cotizar:** se eligió la ruta (`&p=`) y se definió qué pasa con la cantidad y con ids ajenos.
- **Criterio "reconoce que es catering":** se volvió medible (prueba de 5 segundos).
- **Guía de usuario:** todavía no existe (T12 pendiente); se apunta a su futura sección del portal.
- **Pruebas:** no hay e2e del portal ni pruebas de accesibilidad con sesión de cliente; se agregaron al plan.
- **Plan detallado:** sección 9 nueva.

## Fuentes

- hamen/material-3-skill: https://github.com/hamen/material-3-skill
- anthropics/skills, `frontend-design`: https://github.com/anthropics/skills
- material-color-utilities: https://github.com/material-foundation/material-color-utilities
- @vite-pwa/assets-generator: https://github.com/vite-pwa/assets-generator
