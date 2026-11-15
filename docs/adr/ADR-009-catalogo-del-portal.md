# ADR-009 — Catálogo de pymes y productos en el portal de clientes

- Estado: **aceptado** (15-nov-2026, pedido del usuario; plan en `docs/RENOVACION.md`, tarea T15).
- Contexto en: ADR-007 (portal de clientes), ADR-004 (offline), ADR-008 (identidad visual).

## Contexto

En el portal (ADR-007) el cliente elegía la pyme en un `<select>` dentro de la pantalla de cotizar y solo veía los
nombres de los productos en las listas del formulario. No podía **mirar** qué ofrece cada pyme antes de cotizar. El
usuario pidió "un catálogo de productos de las pymes para la vista del cliente: selecciona una pyme y ve sus
productos". Delegó los detalles (15-nov-2026) y pidió implementar todo, con datos de una pyme ficticia de demo.

## Decisión

1. **Flujo:** inicio del cliente → "Pymes" (`#/pymes`) → tarjeta de la pyme (`#/pymes/:id`) → "Cotizar con esta pyme"
   (`#/cotizar?pyme=<id>&p=<ids>`): 3 clics. El cliente puede marcar productos ("Agregar") y llegan a la cotización
   como líneas con el producto elegido, la cantidad vacía y la unidad sugerida según el rendimiento de la receta.
   - Los productos se pasan **por la ruta**: sobrevive a recargar, funciona sin red y no agrega estado compartido.
     Los ids que no son de esa pyme se descartan en la web y la API los vuelve a validar (422 `product_not_found`).
2. **Sin precios en el catálogo.** El precio sale al cotizar (ADR-007), con el margen de la pyme y "precio por
   confirmar" si falta un dato. Nunca costos, margen, insumos, proveedores ni stock: lo asegura una **prueba de lista
   blanca** de las claves de `ProductOut` y `PortalPymeOut`.
3. **Versión completa** (migración `3f9c1a7d2b64`, reversible):
   - `pyme.description` (≤ 280) y `pyme.logo_path`.
   - `recipe.catalog_description` (≤ 500), `recipe.category` (≤ 60), `recipe.photo_path` y
     `recipe.visible_in_catalog` (por defecto `true`: nada cambia para lo que ya existía).
   - `visible_in_catalog = false` saca el producto de **todo** el portal: catálogo, extractor y solicitudes comparten
     `portal.service.products()`. Una sola regla.
   - Solo la **dueña** publica (logo, fotos, descripción, categoría, visibilidad): es una decisión comercial. La
     colaboradora sigue pudiendo editar la receta, pero no el catálogo de imágenes (403).
4. **Imágenes** (`app/core/media.py`):
   - JPEG, PNG o WebP de hasta 2 MB (`MEDIA_MAX_UPLOAD_MB`), tope de 40 MP. Se **re-codifican** a WebP (logo 512 px con
     transparencia, foto 800 px), se corrige la orientación y se **borra el EXIF** (ubicación GPS incluida).
   - Se guardan en el disco del servidor, en `STORAGE_DIR/media/<pyme_id>/<sha256>.webp` (la carpeta que ya usan los
     documentos y que entrará en los respaldos de T11). Se descartaron el almacenamiento de objetos (otro servicio que
     pagar y operar) y "solo URL externa" (no funciona offline y avisa a un tercero quién mira).
   - Se sirven **sin sesión** desde `GET /portal/media/<pyme_id>/<archivo>`, porque un `<img>` no envía el token
     *Bearer*. El nombre es el hash del contenido: no se adivina y nunca cambia, así que se cachea para siempre
     (`immutable`). Se descartó pedirlas con `fetch` + `blob:` (más código y sin caché del navegador).
   - **Cambio respecto al plan:** el plan proponía servir solo imágenes de pymes con portal abierto. Se sirven todas
     las que existan, para que la dueña vea la vista previa aunque su portal esté cerrado. La protección es que la URL
     no se adivina y solo aparece en respuestas del portal o de la propia pyme. Se avisa en pantalla que son públicas.
5. **Offline:** la lista de pymes y los productos se guardan con `useCached` (`portal:pymes`,
   `portal:products:<id>`), con el aviso "datos guardados el…". Las imágenes van a un caché de Workbox *CacheFirst*
   (máx. 100, 30 días). Cotizar sigue necesitando red.
6. **Demo:** la pyme ficticia "Banquetería Volcán Llaima (demo)" trae descripción, logo inventado (volcán sobre verde
   araucaria, generado con Pillow), categorías, textos de catálogo y un producto oculto (`apply_catalog` en
   `demo_full.py`, idempotente: también completa una demo ya creada). No tiene fotos de productos: no se usan fotos
   ajenas ni generadas que parezcan reales; se ve el marcador de la cloche.

## Consecuencias

- El cliente ve qué ofrece cada pyme y empieza a cotizar con los productos ya elegidos.
- Los archivos reemplazados quedan en el disco (hash de contenido); falta una limpieza de huérfanos (T11).
- Publicar precios "desde $X" sigue abierto: requiere validar con una pyme real si quiere mostrarlos.
