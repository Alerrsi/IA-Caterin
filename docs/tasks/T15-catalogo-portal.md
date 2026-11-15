# T15 — Catálogo de pymes y productos para el cliente
- Estado: hecha (falta validar con una pyme y clientes reales)
- Depende de: T13, T14
- Funcionalidad: F3

## Objetivo
Que el cliente de una pyme de catering pueda mirar qué pymes hay y qué ofrece cada una, y empezar a cotizar con los
productos que le interesan en 3 clics, sin ver nunca costos ni datos internos.

## Contexto y decisiones previas
- Plan: `docs/RENOVACION.md` (secciones 3 y 9). Decisión: [ADR-009](../adr/ADR-009-catalogo-del-portal.md).
- Base: portal de clientes (ADR-007, T13) e identidad visual (ADR-008, T14).
- Supuestos explícitos (el usuario delegó los detalles el 15-nov-2026 y pidió "implementar todo" con una pyme ficticia):
  versión completa del catálogo sin esperar la validación con una pyme real; sin precios; imágenes en el disco del
  servidor; solo la dueña publica.

## Entregables
- [x] Migración reversible `3f9c1a7d2b64`: descripción y logo de la pyme; descripción, categoría, foto y visibilidad
      del producto.
- [x] `app/core/media.py`: re-codificación a WebP sin EXIF, topes de tamaño y píxeles, nombres por hash.
- [x] Rutas: `PUT/DELETE /pyme/logo`, `PUT/DELETE /recipes/{id}/photo` (solo dueña), `GET /portal/media/...`
      (público); campos nuevos en `PymeOut`, `RecipeOut`, `PortalPymeOut` y `ProductOut`; filtro
      `visible_in_catalog` en `portal.service.products()`.
- [x] Web del cliente: `PortalPymes.tsx` (lista, buscador sin tildes, logo o inicial), `PortalPyme.tsx` (productos
      por categoría, marcar, cotizar), destino "Pymes" en la navegación y acceso en el inicio.
- [x] `NewQuote` recibe los productos elegidos (`&p=`), descarta ids ajenos y sugiere la unidad.
- [x] Web de la dueña: "Tu vitrina en el portal" en Ajustes (logo y presentación) y "En el catálogo del portal" en la
      receta (foto, descripción, categoría, mostrar u ocultar); `components/ImagePicker.tsx`.
- [x] Offline: lista y productos con `useCached`; imágenes con Workbox *CacheFirst*.
- [x] Datos de demo: catálogo de Volcán Llaima (`apply_catalog`).
- [x] Docs: ADR-009, `API.md`, `DATA_MODEL.md`, `SECURITY.md`, ADR-004, `THIRD_PARTY_NOTICES.md`.

## Criterios de aceptación
| Criterio | Cómo se verifica | Resultado |
|---|---|---|
| Del inicio a cotizar en 3 clics | `Catalog.test.tsx` ("del inicio a cotizar…") y `e2e/portal.e2e.ts` | Cumple |
| Ninguna respuesta del catálogo trae costos, margen, insumos, proveedores ni stock | `test_catalog_responses_only_have_allowed_fields` (lista blanca) | Cumple |
| Sin cuenta, no se ven productos de una pyme con el portal cerrado | `test_cannot_quote_to_a_pyme_with_closed_portal` | Cumple (404) |
| La pyme A no cambia fotos de la B; colaboradora y cliente no publican; 413 y 415; sin EXIF | `test_image_upload_limits_and_roles`, `test_owner_publishes_logo_photo_and_details` | Cumple |
| La ruta de imágenes no se sale de la carpeta | `test_media_route_only_serves_hashed_files` | Cumple |
| Producto oculto fuera de todo el portal | `test_hidden_product_leaves_the_whole_portal` y e2e | Cumple |
| Accesibilidad AA en las pantallas nuevas | `e2e/a11y.e2e.ts` ("portal del cliente y catálogo") | Sin violaciones serias |
| Funciona sin red con lo ya visto | `e2e/pwa.e2e.ts` (catálogo y logo sin red) | Cumple |
| Capturas a 390 px | `apps/web/e2e-artifacts/pymes-390.png`, `pyme-productos-390.png` | Generadas |

Comandos: `docker compose -f infra/docker-compose.yml exec api pytest tests/test_portal.py`, `npm --prefix apps/web test`,
`cd apps/web && npx playwright test e2e/portal.e2e.ts e2e/a11y.e2e.ts` y, con `vite build` + `vite preview`,
`PWA_BASE_URL=http://localhost:4173 npx playwright test e2e/pwa.e2e.ts`. Los datos de demo:
`docker compose -f infra/docker-compose.yml exec api python -m app.db.demo_full`.

## Pruebas requeridas
- API (`tests/test_portal.py`): lista blanca, publicación completa, producto oculto, límites y roles, ruta de imágenes.
  `tests/test_demo_full.py`: la demo trae logo, descripción y categorías.
- Web: `src/pages/portal/Catalog.test.tsx` (6 casos) y `src/pages/CatalogAdmin.test.tsx` (4 casos).
- E2E: `portal.e2e.ts`, `a11y.e2e.ts`, `pwa.e2e.ts`.

## Fuera de alcance
- Precios en el catálogo ("desde $X"), carrito con compra, pagos, reseñas y favoritos.
- Limpieza de imágenes huérfanas (T11).

## Riesgos y preguntas abiertas
- **No validado con personas:** falta mostrarlo a una pyme y a clientes reales (¿quieren fotos?, ¿precios "desde"?).
- Las imágenes son públicas por URL; la pantalla lo avisa. Si una pyme necesita privacidad, cerrar su portal no borra
  las imágenes: hay que quitarlas.
- `e2e/vision.e2e.ts` falla en el entorno de desarrollo actual porque la API ya tiene cargado el modelo de prueba
  `synth-recetas-nano-1` (T06) y la prueba supone que no hay modelo (503). No lo causa esta tarea; corresponde a T06/T10.

## Resumen de cierre
El cliente tiene un catálogo: lista de pymes con logo y presentación, productos agrupados por categoría con foto o
marcador, y un botón para cotizar con los productos ya elegidos. La dueña publica logo, presentación, foto,
descripción y categoría, y puede ocultar productos. Las imágenes se limpian de metadatos y funcionan sin red. Sin
precios ni datos internos, verificado con una prueba de lista blanca. Pendiente: validar con personas reales.
