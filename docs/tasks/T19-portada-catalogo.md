# T19 — Portada del catálogo de una pyme en el portal
- Estado: hecha (16-nov-2026), integrada a `main` el 17-nov-2026
- Rama: `feat/T19-portada-catalogo`
- Depende de: T15 (catálogo del portal, ADR-009), T16 (estética "plano de cocina", ADR-010)
- Funcionalidad: F3 (portal de clientes)
- Decisión: [ADR-012](../adr/ADR-012-portada-del-portal.md)

## Objetivo
Que el cliente final, al entrar a la página de una pyme, vea primero su comida en grande y entienda en un vistazo qué
ofrece y cómo cotizar, como en una vitrina. Hoy la página es una lista ordenada pero plana: no hay un producto que
invite a cotizar.

## Contexto y decisiones previas
- Pedido del usuario (16-nov-2026): implementar una interfaz basada en una imagen de referencia de una landing de
  comida (tendencia "títulos o imágenes en gran tamaño"): título grande en dos tonos, foto del plato muy grande sobre un
  panel oscuro con corte diagonal, elementos pequeños "flotando", precio, botón con ícono, una tarjeta punteada tipo
  cupón con otro producto y un bloque con avatar.
- Se toman los **principios**, no la marca de la referencia (sin su logo, textos, colores, amarillo ni píldoras).
- Reglas que no cambian: ADR-007 (el cliente no ve costos, margen ni stock), ADR-009 (catálogo sin precios: el precio
  sale al cotizar), ADR-008/010 (laurel, cobre solo como detalle, IBM Plex, esquinas casi rectas, cifras en Mono, líneas
  finas), AA, mobile first a 390 px, PWA sin red (sin imágenes externas ni CDN).

### Supuestos (decididos sin preguntar)
1. **Pantalla:** la página de una pyme en el portal (`pages/portal/PortalPyme.tsx`). Es donde se vende comida al
   cliente final. El resto del portal y las pantallas de la pyme no cambian.
2. **Sin precio en la portada.** La referencia muestra precio tachado y precio actual, pero la API del portal no entrega
   precios (ADR-009) y no se inventan. En su lugar va, en Mono, cómo se vende ("Por unidad") y "Precio al cotizar".
   Tampoco se tacha nada: sugeriría una oferta que no existe.
3. **Producto destacado (regla determinista):** el primer producto, en el orden del catálogo (categorías con más
   productos primero), que tenga foto; si ninguno tiene foto, el primero con descripción; si tampoco, el primero.
   **Recomendado** (tarjeta tipo cupón): el siguiente con el mismo criterio, distinto del destacado. Con un solo
   producto no hay cupón.
4. **Título en dos tonos, no en dos pesos:** la marca solo carga IBM Plex Serif 500 (no se agregan pesos). La primera
   palabra del nombre va en `on-surface-variant` y el resto en `on-surface` ("Empanadas / de pino").
5. **Panel laurel rayado** (`bg-brand hatch`) con corte diagonal por `clip-path` detrás de la foto. Es una excepción
   acotada a la regla de "un solo momento fuerte" (ADR-012): la portada del portal es la vitrina para clientes, no una
   pantalla de trabajo.
6. **"Ingredientes flotando" → marcas del plano:** cuadrados pequeños con borde fino y un punto cobre (detalle), solo
   decorativos (`aria-hidden`), sin animación.
7. **Bloque con avatar → la pyme:** su logo o inicial (`PymeAvatar`), nombre y comuna, como la "recomendación del chef".
8. **Botones:** los de la marca (`<Button>`, esquina de 4 px). El de la portada dice "Cotizar {producto}" y lleva a
   cotizar con ese producto ya elegido (más los que el cliente haya marcado).
9. **Sin foto:** marco punteado con `grid-paper` y el ícono `cloche` (la demo no tiene fotos de productos).

## Entregables
- [x] Plan (este documento) y ADR-012
- [x] Portada de la pyme: título en dos tonos, bajada, "cómo se vende", botón, foto grande sobre panel laurel diagonal,
      marcas decorativas, bloque de la pyme
- [x] Tarjeta punteada "Recomendado" con su botón Agregar
- [x] Grilla del catálogo con fotos más grandes
- [x] Textos en `i18n.ts`; pruebas Vitest; e2e con capturas a 390 y 1280 px (con y sin fotos)

## Criterios de aceptación
- `/pymes/{id}` muestra la portada con el producto destacado según la regla; "Cotizar {producto}" lleva a
  `#/cotizar?pyme={id}&p={producto}`.
- Sin precios ni datos internos en la página (`$` no aparece).
- 390 y 1280 px sin scroll horizontal; axe sin violaciones serias; contraste AA; `motion-reduce` respetado.
- `npm run lint`, `npm run typecheck`, `npm test` y `npm run theme -- --check` pasan.

## Pruebas requeridas
- Vitest: regla del destacado y del recomendado (con foto, sin foto, un solo producto); botón de la portada; tarjeta
  recomendada marca el producto; sin `$`.
- e2e: capturas a 390 y 1280 px con la demo (sin fotos) y con fotos de prueba inyectadas en la respuesta (sin tocar la
  base); sin scroll horizontal; axe.

## Fuera de alcance
- Precios en el catálogo, ofertas o cupones de descuento reales.
- Cambiar la página de lista de pymes o las pantallas de la pyme.
- Animaciones de entrada.

## Riesgos y preguntas abiertas
- Sin fotos reales la portada pierde fuerza: conviene pedir a las pymes una foto del producto estrella.
- Validar con clientes reales si prefieren ver la portada o ir directo a la lista.

## Resumen de cierre
**Qué se hizo (16-nov-2026):** portada en `pages/portal/PortalPyme.tsx` (`Showcase`, `Recommended`, `pickShowcase`,
`splitTitle`): producto destacado en Serif grande en dos tonos, bajada, "Por unidad / Precio al cotizar" en Mono,
botón "Cotizar {producto}" (lleva el destacado y lo ya marcado), foto en marco punteado girado 2° sobre el panel laurel
rayado con corte diagonal (celular: arriba con corte inferior; escritorio: columna derecha), marcas del plano y un
punto cobre como adornos, bloque "Lo prepara" con la pyme y "Ver los N productos" (desplaza a la grilla, sin animación
con movimiento reducido), y tarjeta punteada "Recomendado" con su botón Agregar (comparte el estado con la grilla).
Miniaturas de la grilla en el celular de 80 a 96 px. ADR-012 y excepción anotada en la skill `caterin-brand`.

**Pruebas:** Vitest 150 (2 nuevas: regla del destacado y portada con botón y recomendado); `e2e/portada.e2e.ts` con la
demo sin fotos y con fotos de prueba inyectadas en la respuesta (sin tocar la base): sin scroll horizontal a 390 y
1280 px y axe sin violaciones serias. `portal.e2e.ts` y `a11y.e2e.ts` pasan. Lint, typecheck y tema al día.

**Pendiente:** fotos reales de productos (la demo no tiene); validar con clientes si la portada ayuda a cotizar.

**Riesgos:** sin fotos la portada se apoya en el vacío del plano; el título grande alarga la pantalla en el celular
(la foto queda primero y el título justo debajo).
