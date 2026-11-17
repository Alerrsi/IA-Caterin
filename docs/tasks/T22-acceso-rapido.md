# T22 — Acceso rápido: todo a uno o dos toques
- Estado: hecha en la rama `feat/T22-acceso-rapido` (falta integrar a `main` y validar con una emprendedora real)
- Depende de: T21 (estética nueva de toda la app)
- Funcionalidad: transversal

## Objetivo
Que la emprendedora llegue a cualquier pantalla, dato o acción **rápido y sin pensar**: desde cualquier parte, en
uno o dos toques en el celular, o escribiendo lo que busca. AGENTS.md pide "máximo 3 clics para las acciones
principales"; esta tarea lo baja a 2 y lo verifica con pruebas.

## Diagnóstico (16-nov-2026, antes de T21)
- **Celular:** la barra inferior tiene 4 destinos (Inicio, Cotizar, Pedidos, Preguntar). Contar con foto,
  Inventario, Recetas, Mi negocio, Importar, Métricas y Ajustes exigen abrir el menú (2 toques). Contar con foto e
  Inventario son de uso diario.
- **No hay búsqueda global:** para llegar a un insumo, receta, pedido o proveedor hay que entrar a su lista y buscar.
  El atajo `/` solo funciona dentro de Inventario y del directorio de pymes.
- **Volver siempre va al inicio:** 18 pantallas usan `onBack={() => navigate('/')}`. Si llegaste a una receta desde un
  pedido, pierdes dónde estabas.
- **Teclado y lector de pantalla:** no hay enlace "Saltar al contenido"; al cambiar de pantalla el foco no va al título
  ni se anuncia la pantalla nueva.
- **Avisos del inicio:** "3 insumos bajo el mínimo" abre la lista completa, no la filtrada.

## Supuestos (decididos sin preguntar; ver memoria "decidir detalles sin preguntar")
1. "Accesible" se entiende como **rápido y fácil de alcanzar** (pedido del usuario) y, de paso, accesible por teclado
   y lector de pantalla (WCAG 2.1 AA, que ya es regla del proyecto).
2. Barra inferior de la dueña con 5 espacios: **Inicio · Cotizar · Foto · Inventario · Más**. "Más" abre una hoja con
   todo lo demás en una grilla de botones grandes, agrupada (Ventas: Pedidos, Preguntar, Mi negocio; Cocina: Recetas,
   Productos listos; Administración: Importar, Métricas, Ajustes). Pedidos y Preguntar siguen a un toque desde el
   inicio. La colaboradora y el cliente del portal conservan sus barras, con el mismo patrón.
3. **Buscador global ("¿Qué necesitas?")** en la cabecera de todas las pantallas, con `Ctrl/⌘ K` y `/` en escritorio:
   busca acciones ("cotizar", "nuevo insumo", "contar con foto", "ajustar stock") y datos (insumos, recetas, pedidos
   por cliente o fecha, proveedores), sin tildes y con coincidencia aproximada. Usa las listas ya guardadas en el
   teléfono (funciona sin red) y no llama a la IA.
4. Volver usa el historial cuando existe y, si se entró directo por un enlace, va al padre lógico (receta → Recetas).
5. Los avisos y accesos llevan a la vista **ya filtrada** mediante la URL (`/inventario?bajo=1`,
   `/pedidos?estado=requested`), así también se pueden guardar o compartir.
6. **"Seguir donde quedaste"** en el inicio: los últimos 3 elementos abiertos (insumo, receta, pedido), guardados solo
   en el teléfono.

## Plan de implementación
1. `AppShell`: barra de 5 con "Más" (hoja inferior accesible: `dialog`, foco atrapado, Esc cierra), y en escritorio
   la barra lateral con todo visible y agrupado igual.
2. `components/QuickFind.tsx`: combobox ARIA 1.2 (lista de resultados con flechas, Enter abre, Esc cierra), resultados
   agrupados (Acciones, Insumos, Recetas, Pedidos, Proveedores), máximo 8, con su ícono; datos desde `useCached`.
   Botón con lupa en la cabecera y atajos `Ctrl/⌘ K` y `/` (el `/` local de Inventario sigue enfocando su buscador).
3. Navegación: helper `goBack(fallback)` y reemplazo de los 18 `navigate('/')`; filtros leídos desde la URL en
   Inventario y Pedidos; avisos del inicio con esos enlaces.
4. Accesibilidad de base: enlace "Saltar al contenido", foco al `h1` y anuncio en una región `aria-live` al cambiar de
   pantalla, `aria-current` en la navegación, objetivos táctiles de 48 px, orden de tabulación revisado.
5. Atajos de escritorio visibles en una ayuda (`?`): `C` cotizar, `F` foto, `I` inventario, `P` pedidos,
   `Ctrl/⌘ K` buscar. Nunca actúan dentro de un campo.
6. Inicio: "Acciones rápidas" (Cotizar, Contar con foto, Ajustar stock, Preguntar) y "Seguir donde quedaste".

## Pruebas
- e2e "mapa de alcance": desde 5 pantallas distintas, a 390 px, cada destino principal se alcanza en ≤ 2 toques
  (se cuentan los clics en la prueba) y cada acción principal (cotizar, contar con foto, ajustar stock, ver pedido) en
  ≤ 3.
- e2e solo con teclado: buscar "harina" con `Ctrl+K`, abrir el insumo, ajustar el stock y volver, sin mouse.
- Vitest del buscador (sin tildes, aproximado, agrupado, sin red), de "Más" (foco atrapado, Esc) y de `goBack`.
- axe sin violaciones serias en todas las pantallas; lector de pantalla: el cambio de pantalla se anuncia.

## Entregables
- [x] Barra de 5 con "Más" y ~~barra lateral~~ agrupación en "Más" (en escritorio quedó la barra superior de T21 con
  Inicio, Cotizar, Foto, Inventario y Pedidos, más el botón "Más" con la misma hoja agrupada; no hay barra lateral)
- [x] Buscador global con acciones y datos, sin red (sin proveedores: ver "Pendiente")
- [x] Volver con historial y filtros en la URL
- [x] Saltar al contenido, foco y anuncio al cambiar de pantalla, ayuda de atajos
- [x] Inicio con acciones rápidas y "Seguir donde quedaste"
- [x] Pruebas de alcance y de teclado; documentación e índice (pasan el 17-nov-2026; ver "Resultados de las pruebas")

## Criterios de aceptación
- Cualquier pantalla principal a ≤ 2 toques desde cualquier otra en el celular, medido por la e2e.
- Cualquier insumo, receta o pedido a ≤ 3 teclas + Enter desde cualquier pantalla con el buscador.
- `./scripts/check.sh`, axe y las e2e nuevas pasan.

## Fuera de alcance
- Búsqueda por voz; búsqueda con IA; personalizar la barra inferior.

## Riesgos y preguntas abiertas
- Cinco espacios en la barra inferior es el máximo cómodo a 390 px; si T21 agranda los íconos, puede bajar a 4 + Más.
- Validar con una emprendedora real cuáles son sus 4 accesos más usados.

## Resumen de cierre
**Qué se hizo (16 y 17-nov-2026):**
- Agregado el 17-nov-2026 para la reunión de demostración (pedido del usuario): botón **Demo** en la fila del logo del
  login que abre una hoja con 4 cuentas ficticias de Banquetería Volcán Llaima (dueña, jefa de cocina, encargada de
  ventas, cliente del portal); un toque entra. Va en la fila que ya existía para no romper "entrar sin scroll" de T21
  (a 360×640 quedaban ~50 px libres). Solo aparece en desarrollo o con `VITE_DEMO_LOGIN=true` (`apps/web/src/demoLogin.ts`).
  Prueba Vitest en `App.test.tsx` y e2e con axe en `acceso-rapido.e2e.ts`; suite e2e completa: 32 aprobadas, 3 omitidas.
- `components/AppShell.tsx`: barra inferior del celular con **Inicio · Cotizar · Foto · Inventario · Más** (dueña y
  colaboradora; el cliente del portal tiene sus 3 destinos + "Más"). "Más" abre la hoja "Todo Cáterin" con botones
  grandes agrupados en Ventas (Pedidos, Preguntar, Mi negocio), Cocina (Recetas, Productos listos) y Administración
  (Importar, Métricas, Ajustes), más "Cerrar sesión". Mi negocio y Administración son solo de la dueña. En escritorio
  (≥ 1024 px) la barra superior de T21 muestra Inicio, Cotizar, Foto, Inventario y Pedidos con su atajo, y un botón
  "Más" que abre la misma hoja. `aria-current` en todos los destinos.
- `components/Dialog.tsx`: diálogo modal común (foco atrapado, Esc y toque fuera cierran, el foco vuelve a donde
  estaba); lo usan "Más", el buscador y la ayuda de atajos.
- Buscador global **"¿Qué necesitas?"** (`components/QuickFind.tsx` + `quickfind.ts`): combobox ARIA 1.2 con flechas,
  Inicio/Fin, Enter y Esc; busca sin tildes, por prefijo, por palabras clave y con errores de tipeo (una letra desde 4
  letras, dos desde 7). Encuentra acciones (cotizar, contar con foto, ajustar stock, nuevo insumo, nueva receta,
  solicitudes, insumos bajo el mínimo, pedidos de los próximos 7 días y cada pantalla) y datos: insumos con su stock,
  recetas, productos listos con existencias y pedidos por cliente, fecha o estado. Al cliente del portal le busca pymes
  y productos del catálogo. Máximo 8 resultados agrupados. Al abrirse pide las listas con `useCached`:
  con señal trae lo último y sin señal usa lo guardado en el teléfono y lo avisa.
  Nunca llama a la IA. Se abre con la lupa de la cabecera,
  `Ctrl/⌘ K` o `/` (en Inventario y en el directorio de pymes `/` sigue enfocando el buscador de la pantalla).
- `router.ts`: rastro de la sesión en memoria y `goBack(fallback)`: "Volver" regresa a la pantalla anterior de la app y,
  si se entró directo por un enlace, al padre lógico (insumo → Inventario, receta → Recetas, cotización → Pedidos).
  `navigate(path, { replace: true })` después de guardar un formulario (nuevo insumo, nueva receta, cotizar), para que
  "Volver" no regrese al formulario enviado. `queryParams` y `replaceQuery` para filtros en la URL. Se reemplazaron
  los `onBack={() => navigate('/')}` de las pantallas por `goBack`.
- Filtros en la URL: `/inventario?bajo=1`, `?q=` y `?ajustar=1` (enfoca el buscador del inventario);
  `/pedidos?estado=requested`, `?proximos=7` y `?pedido=<id>`, con un aviso "Mostrando…" y "Ver todos". Los avisos del
  inicio abren la vista ya filtrada.
- Accesibilidad: botón "Saltar al contenido" como primer elemento con Tab; al cambiar de pantalla (no de filtro) la
  página sube, el foco va al `h1` (salvo que la pantalla haya enfocado un campo) y una región `aria-live` anuncia
  "Pantalla: …". Objetivos táctiles de 48 px o más en la navegación.
- Atajos de escritorio (`shortcuts.ts`, ayuda con `?`): `C` cotizar, `F` contar con foto, `I` inventario, `P` pedidos,
  `/` o `Ctrl/⌘ K` buscar, `?` ayuda. No actúan dentro de un campo ni con un diálogo abierto; el cliente del portal
  solo tiene `C`, `/` y `?`.
- Inicio (`pages/Home.tsx`): "Acciones rápidas" (Cotizar un pedido, Contar con foto, Ajustar stock, Preguntar) y
  "Seguir donde quedaste" (`recent.ts`): los últimos 3 insumos, recetas, cotizaciones o pymes abiertos, guardados solo
  en este teléfono (`localStorage`, por persona). Si el almacenamiento está bloqueado la lista no aparece y la app sigue
  igual.
- Pruebas: `src/quickaccess.test.tsx` (Vitest: normalización, búsqueda aproximada y agrupada, `goBack`, recientes,
  `Ctrl+K`, "Más" con foco atrapado y Esc, avisos filtrados, saltar al contenido y foco al título) y
  `e2e/acceso-rapido.e2e.ts` (mapa de alcance desde 5 pantallas a 390 px, acciones principales en ≤ 3 toques, recorrido
  solo con teclado en escritorio, axe en 12 pantallas a 390 y 1280 px, capturas en `apps/web/e2e-artifacts/t22/`).

**Resultados de las pruebas:**
Ejecutadas el 17-nov-2026 con el compose de desarrollo y la demo de Banquetería Volcán Llaima (datos sintéticos):
- `./scripts/check.sh`: pasa (ruff, mypy; pytest 309 aprobadas, 1 omitida, 1 xfail, cobertura 97 %; eslint, `tsc -b`;
  Vitest 24 archivos, 173 pruebas).
- `npx playwright test e2e/acceso-rapido.e2e.ts`: 4 aprobadas. Suite e2e completa: 31 aprobadas, 3 omitidas (las de
  `pwa.e2e.ts`, que exigen `PWA_BASE_URL` con `vite preview`; no se ejercitaron).
- Mapa de alcance a 390 px, peor caso desde `/`, `/inventario`, `/recetas`, `/pedidos` y `/tablero`: Inicio, Cotizar,
  Contar con foto e Inventario a 1 toque; Pedidos, Preguntar, Mi negocio, Recetas, Productos listos, Importar, Métricas
  y Ajustes a 2. Acciones principales a ≤ 3 toques (en "ajustar stock" la prueba cuenta hasta abrir el ajuste, no el
  guardado).
- axe: sin violaciones serias ni críticas en 12 pantallas a 390 y 1280 px, ni con la hoja "Más" o el buscador abiertos.
- Correcciones al verificar: la prueba de teclado llegaba a "Volver" con `focus()` por código y ahora llega solo con
  `Shift+Tab`; `navigate(…, { replace: true })` hacia la misma ruta dejaba una marca encendida que hacía que "Volver"
  se saltara una pantalla (corregido en `router.ts`, con prueba Vitest).

**Pendiente:**
- Proveedores en el buscador: el plan los incluía y no están (solo acciones, insumos, recetas, productos listos y
  pedidos).
- Barra lateral de escritorio: no se hizo; se mantuvo la barra superior de T21 (ADR-013) con "Más". Si una usuaria de
  computador echa de menos ver todo de una vez, se reevalúa.
- "Seguir donde quedaste" guarda cotizaciones en vez de pedidos (los pedidos se abren desde la lista, sin pantalla
  propia).
- Probar el anuncio con un lector de pantalla real (TalkBack en Android); las pruebas solo verifican la región
  `aria-live` y el foco.
- La e2e cubre a la dueña; la colaboradora y el cliente del portal no tienen mapa de alcance propio.
- Validar con una emprendedora real cuáles son sus 4 accesos más usados.
- Integrar a `main` cuando el usuario lo apruebe.
- Guía de usuaria: todavía no existe (es parte de T12). Cuando se escriba, debe explicar la barra inferior y "Más", el
  buscador "¿Qué necesitas?" y los atajos (`C`, `F`, `I`, `P`, `/` o `Ctrl/⌘ K`, `?`); el detalle técnico quedó en
  `docs/ARCHITECTURE.md` (3.1) y `docs/adr/ADR-004-offline-pwa.md`.

**Riesgos:**
- Cinco espacios en la barra inferior: la e2e mide a 390 px; en celulares de 360 px no se ha probado y las etiquetas
  pueden quedar justas.
- Sin señal, el buscador solo encuentra lo que el teléfono ya guardó: un insumo creado en otro equipo no aparece hasta
  abrir la app con señal.
- Cada vez que se abre, el buscador pide hasta 4 listas (insumos, recetas, productos listos, pedidos); al cliente del
  portal le pide el catálogo de cada pyme del directorio. Con red lenta o muchas pymes puede ser lento o gastar datos;
  si se nota, conviene mostrar primero lo guardado y refrescar en segundo plano.
- El rastro de "Volver" vive en memoria: al recargar la página se pierde y "Volver" va al padre lógico.
