# T08 — Frontend PWA mobile-first
- Estado: hecha (9-nov-2026), salvo la prueba con una persona de fuera del equipo y Lighthouse (ver cierre)
- Depende de: T05, T06, T07 (por pantallas; inicio e inventario pueden empezar tras T04)
- Funcionalidad: transversal

## Objetivo
Una app que la emprendedora use desde su celular con una mano, entre una tanda y otra, en pocos toques, y que no la deje botada cuando se cae la señal.

## Contexto y decisiones previas
- Offline: ADR-004. API: `docs/API.md`. Textos en es-CL desde el archivo i18n, lenguaje simple, botones grandes, contraste AA, máximo 3 toques para las acciones principales (`AGENTS.md`, sección 5).
- Supuesto: celular de gama media Android con Chrome como objetivo principal; iOS Safari como secundario (Background Sync no existe en iOS).

## Entregables
- [x] **Inicio:** accesos grandes a "Cotizar", "Contar con foto", "Inventario", "Preguntar"; alertas de stock bajo y pedidos próximos. (Las alertas salen de lo guardado en el teléfono: se ven sin señal.)
- [x] **Inventario:** lista con búsqueda, ajuste rápido de stock (+/−), detalle con historial, recetas con costo. (El costo lo ve solo la dueña.)
- [x] **Cotizar:** pegar texto o llenar formulario → tabla editable del pedido interpretado → cotización con lista de compras → PDF. (Compartir con la hoja nativa del teléfono: pendiente; hoy se abre o descarga el PDF.)
- [x] **Mis pedidos:** lista con "Cotizar" o "Ver cotización".
- [x] **Foto de producción:** cámara → conteo con cajas → corregir con +/− → confirmar. (Sin modelo cargado o sin señal: registro a mano; sin señal también se puede guardar la foto para contarla después.)
- [x] **Chat:** botones de preguntas frecuentes, respuesta en *streaming*, fuente visible, pulgar arriba/abajo. (Opciones de aclaración como botones; evento `replace` cuando el LLM inventa una cifra; aviso sin conexión.)
- [x] Importar planillas (vista previa de errores) y configuración básica (merma, margen, IVA). (Importar permite deshacer la carga.)
- [x] Login, registro e invitar colaboradora.
- [x] PWA: instalable, app shell en caché, catálogos en IndexedDB, cola de escrituras con `Idempotency-Key`, banner de sin conexión y contador de pendientes. (Detalle en ADR-004, sección Implementación.)
- [x] Encuesta de 1 a 5 estrellas (para T09), no invasiva. (Tras cotizar, tras confirmar una producción y tras dos respuestas del asistente; sin señal va a la cola.)

## Criterios de aceptación
- Las acciones principales (ajustar stock, iniciar una cotización, sacar una foto, hacer una pregunta frecuente) toman ≤ 3 toques desde el inicio.
- Lighthouse (móvil): accesibilidad ≥ 90 y PWA instalable. axe sin errores críticos en las pantallas clave.
- Con la red cortada: la app abre, muestra inventario y recetas cacheadas, permite ajustar stock, y los cambios se envían al volver sin duplicarse.
- Usable a 360 px de ancho sin scroll horizontal.
- Todos los textos visibles salen del archivo i18n.

## Pruebas requeridas
- Vitest: componentes y la cola offline (reintentos, idempotencia, conflictos).
- Playwright (perfil móvil): flujos de cotización, foto (con imagen de prueba), chat y offline (`context.setOffline(true)`).
- Prueba con al menos una persona fuera del equipo (idealmente una emprendedora): anotar dónde se trabó.

## Fuera de alcance
- App nativa, modo oscuro (opcional si sobra tiempo), personalización de marca en el PDF.

## Riesgos y preguntas abiertas
- Cámara en iOS dentro de una PWA instalada: verificar el comportamiento de `<input capture>`.
- El tamaño del bundle afecta la carga con mala señal: presupuesto propuesto ≤ 250 KB de JS comprimido en la carga inicial (a medir).

## Resumen de cierre
**Avance parcial (9-nov-2026) — pantallas de F3:**
- Router por hash sin dependencias (`src/router.ts`), cliente API con token en memoria, refresh automático ante 401 y problem+json (`src/api.ts`), sesión (`src/auth.tsx`), formatos es-CL (`src/format.ts`), textos en `src/i18n.ts`.
- Pantallas: login, inicio, cotizar (pegar mensaje o formulario → tabla editable con sugerencias → pedido → cotización), cotización (totales, productos, aviso de precios faltantes, PDF, estados, lista de compras), mis pedidos. Banner "Sin conexión".
- Verificado: lint, typecheck, 9 pruebas de Vitest, build (precache 253 KB) y 1 e2e de Playwright con el Chromium del sistema (login → 24 sopaipillas a mano → total $11.681 → PDF 200). Captura a 390 px revisada.
- Pendiente: inventario, recetas, proveedores, importar, configuración, registro e invitación, foto, cola offline e IndexedDB, encuesta, auditoría de accesibilidad.
- El e2e deja en la base de desarrollo un pedido "Cliente E2E (demo)".

**Avance (9-nov-2026) — pantalla Preguntar (F1):**
- `src/pages/Assistant.tsx` en `#/preguntar`, habilitada desde el inicio (2 toques para una pregunta frecuente). Cliente SSE en `src/api.ts` (`askAssistant`): lee el cuerpo en *streaming*, tolera eventos partidos entre trozos y, si el servidor responde JSON, lo trata como un solo `done`. El texto del modelo se muestra como texto plano.
- Verificado: lint, typecheck, 21 pruebas de Vitest (5 nuevas: *streaming*, `replace`, acciones rápidas y opciones, error de la API, sin conexión) y 2 e2e de Playwright a 390 px. El e2e nuevo comprueba que no haya scroll horizontal. El SSE pasa por el proxy de Vite sin quedar en búfer (probado con `curl`).
- **Lo que encontró el e2e (corregido):** (1) la fila del campo y el botón desbordaba 390 px (faltaba `min-w-0`); (2) en la API, tocar la opción "Crema de leche" volvía a preguntar "¿A cuál insumo?", porque "leche" también calzaba con "Leche". Ahora gana la coincidencia exacta más larga, y una prueba de la API verifica que cada opción de aclaración se resuelva.

**Cierre (9-nov-2026) — resto de las pantallas y modo sin conexión.** Desarrollado en paralelo por tres agentes (inventario y recetas; foto; ajustes, importar y registro) sobre una base común (rutas, textos y capa offline) e integrado después.
- **Pantallas nuevas:** inicio con avisos, inventario (lista, +/− en la fila, detalle con historial), recetas (insumos y costo para la dueña), foto de producción (cajas sobre la foto, −/+ por producto, receta obligatoria para clases sin receta, registro a mano), ajustes (pyme y equipo, invitar colaboradora), importar (plantilla, revisión con errores por fila, carga y deshacer) y registro.
- **Sin conexión** (`src/offline/`): catálogos guardados en IndexedDB por pyme, cola con `Idempotency-Key` (se reusa la misma clave al reintentar), banner con pendientes y fallidas, fotos guardadas (≤ 1280 px, tope 20) y apertura sin red con la última sesión (sin tokens).
- **Verificado:**
  - typecheck y lint limpios; **56 pruebas de Vitest** en 11 archivos;
  - **8 e2e de Playwright** a 390 px con el Chromium del sistema (cotización, chat, inventario con y sin señal, foto, ajustes e importar, y accesibilidad), todas sin scroll horizontal;
  - **axe (WCAG 2.1 A/AA) sin violaciones serias ni críticas** en login, registro y las 10 pantallas con sesión;
  - la build de producción con service worker abre sin red y muestra el inventario guardado (`e2e/pwa.e2e.ts`, contra `vite preview`);
  - JS inicial de 92,5 KB comprimido, dentro del presupuesto propuesto de 250 KB.
- **Toques:** una pregunta frecuente, 2 desde el inicio; ajustar stock, 3 (Inventario → + → Guardar); iniciar una cotización, 1; sacar una foto, 2.
- **No hecho:**
  - **Lighthouse**: no se corrió, porque el permiso para descargarlo y ejecutarlo fue denegado en esta sesión. La accesibilidad está cubierta por axe. Falta medir Lighthouse (móvil, accesibilidad ≥ 90) y revisar la instalabilidad en un Android real.
  - **Prueba con una persona de fuera del equipo** (depende de la pregunta 6 del índice).
  - **Compartir el PDF** con la hoja nativa del teléfono.
  - **Diálogo de conflicto** para catálogos editados sin señal: hoy, sin señal solo se envían movimientos, así que no aplica.
- **Restos en la base de desarrollo:** las e2e dejan 1 `production_record` (1 empanada de pino), dos movimientos de "Sal" (+1 kg y −1 kg, el stock queda igual) y un pedido "Cliente E2E (demo)" por cada corrida de la e2e de cotización.
- **Riesgos:** las fotos guardadas y la cola viven en el navegador. Si la usuaria borra los datos del sitio antes de volver la señal, se pierden. La guía de usuaria (T12) debe decirlo.

## Rediseño con Material Design 3 (10-nov-2026, pedido del usuario)

- **Colores neutros con roles de MD3** (`apps/web/src/index.css`): primary, secondary-container, surface-container,
  on-surface-variant, outline y los demás. Las pantallas usan el rol, no un color fijo, así cambiar la paleta es
  cambiar un solo archivo. Los avisos (advertencia, información, éxito) usan contenedores apagados para no romper la
  paleta neutra.
- **Componentes** (`components/ui.tsx`):
  - botones MD3: relleno, tonal, delineado y de texto, con forma de píldora y 48 px de alto mínimo;
  - campos de texto delineados, tarjetas delineadas, chips de estado y alertas con ícono.
  - Íconos de Material Icons en SVG en línea (`components/Icon.tsx`), sin fuentes externas, para que la PWA siga
    funcionando offline.
- **Diseño de escritorio que se adapta al celular** (`components/AppShell.tsx`):
  - Desde 1024 px: cajón de navegación fijo a la izquierda, y contenido de hasta 1152 px con grillas (inicio como
    panel, pedidos, inventario y recetas en columnas, cotización con el total y las acciones fijos a la derecha).
  - Más angosto: barra superior con menú (cajón modal) y barra de navegación inferior con 4 destinos.
  - Los formularios de una columna usan `Page size="narrow"`.
- **Verificación:** tipos, lint y 76 pruebas de interfaz, más una revisión visual con capturas a 1440×900 y 390×844
  (inicio, pedidos, inventario, ajustes y portal del cliente).
- **Sin verificar:** las pruebas e2e con navegador (Playwright) después del rediseño, Lighthouse y el contraste medido
  con herramienta (los pares de colores se eligieron con contraste AA, revisado a mano).
