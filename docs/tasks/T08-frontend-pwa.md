# T08 — Frontend PWA mobile-first
- Estado: en curso (pantallas de F3 hechas)
- Depende de: T05, T06, T07 (por pantallas; inicio e inventario pueden empezar tras T04)
- Funcionalidad: transversal

## Objetivo
Una app que la emprendedora use desde su celular con una mano, entre una tanda y otra, en pocos toques, y que no la deje botada cuando se cae la señal.

## Contexto y decisiones previas
- Offline: ADR-004. API: `docs/API.md`. Textos en es-CL desde el archivo i18n, lenguaje simple, botones grandes, contraste AA, máximo 3 toques para las acciones principales (`AGENTS.md`, sección 5).
- Supuesto: celular de gama media Android con Chrome como objetivo principal; iOS Safari como secundario (Background Sync no existe en iOS).

## Entregables
- [ ] **Inicio:** accesos grandes a "Cotizar", "Contar con foto", "Inventario", "Preguntar"; alertas de stock bajo y pedidos próximos.
- [ ] **Inventario:** lista con búsqueda, ajuste rápido de stock (+/−), detalle con historial, recetas con costo.
- [x] **Cotizar:** pegar texto o llenar formulario → tabla editable del pedido interpretado → cotización con lista de compras → PDF. (Compartir con la hoja nativa del teléfono: pendiente; hoy se abre o descarga el PDF.)
- [x] **Mis pedidos:** lista con "Cotizar" o "Ver cotización".
- [ ] **Foto de producción:** cámara → conteo con cajas → corregir con +/− → confirmar.
- [ ] **Chat:** botones de preguntas frecuentes, respuesta en *streaming*, fuente visible, pulgar arriba/abajo.
- [ ] Importar planillas (vista previa de errores) y configuración básica (merma, margen, IVA).
- [ ] Login, registro e invitar colaboradora.
- [ ] PWA: instalable, app shell en caché, catálogos en IndexedDB, cola de escrituras con `Idempotency-Key`, banner de sin conexión y contador de pendientes.
- [ ] Encuesta de 1 a 5 estrellas (para T09), no invasiva.

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
- Pendiente: inventario, recetas, proveedores, importar, configuración, registro e invitación, foto, chat, cola offline e IndexedDB, encuesta, auditoría de accesibilidad.
- El e2e deja en la base de desarrollo un pedido "Cliente E2E (demo)".
