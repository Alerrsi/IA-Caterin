# T21 — Rediseño de toda la app con la estética de la imagen de referencia
- Estado: en curso
- Rama: `feat/T21-estetica-referencia` (parte de `main` + T18 + T19)
- Depende de: T18, T19
- Funcionalidad: transversal
- Decisión: [ADR-013](../adr/ADR-013-estetica-de-la-referencia.md) (reemplaza ADR-008 y ADR-010)

## Objetivo
Que la app se vea como la imagen de referencia que eligió el usuario: blanca y limpia, con un gran panel oscuro en
diagonal, platos de comida enormes, títulos grandes en dos pesos y botones en píldora con acento amarillo. Que la
emprendedora y sus clientes sientan que es una app de comida, no una planilla.

## Contexto y decisiones previas
- Pedido del usuario (16-nov-2026): tras ver T19 dijo "yo no veo el diseño como el de la foto" y eligió "toda la app",
  "muy fiel" y "fotos libres".
- Imagen: `/home/alerrsi/Music/Tendenciaendisenowebtitulosoimagenesengrantamano2.webp` (no se versiona: es material de
  un tercero; se toman rasgos, no su marca).
- Se mantienen: AA, botones de 48 px, foco visible, `motion-reduce`, es-CL, PWA sin red, ADR-007 (el cliente no ve
  datos internos), nunca inventar precios.

### Supuestos
1. Fuente Urbanist (OFL) por ser geométrica y parecida a la de la referencia; variable, autoalojada.
2. Colores exactos en ADR-013. El amarillo es solo fondo; para texto/acento sobre blanco, ámbar oscuro.
3. Las fotos de comida las trae **otro agente** en esta misma rama (licencia libre, registro en
   `THIRD_PARTY_NOTICES.md`, asignación idempotente a la demo). Contrato: `apps/web/public/fotos/plato-hero.webp`,
   `plato-2.webp`, `plato-3.webp` (platos redondos, fondo transparente) e `ingrediente-{albahaca,tomate,limon,aji}.webp`
   (para flotar); las fotos de productos llegan por `photo_url`. Mientras no existan, el diseño se ve bien con el vacío.
4. El bloque "recomendación" usa el logo o la inicial de la pyme en el círculo, no la foto de una persona.
5. En escritorio la navegación pasa a una barra superior; en el celular se mantienen la barra superior y la inferior.

## Entregables
- [ ] ADR-013, skill `caterin-brand` y `.interface-design/system.md` al día
- [ ] Tokens (`scripts/theme.mjs`), fuente, radios, sombras y patrón `doodles`
- [ ] Componentes base (`ui.tsx`, `AppShell`, `Logo`, `charts.tsx`)
- [ ] Entrar/registro con portada de plato grande
- [ ] Portal: portada de la pyme casi como la imagen, directorio y catálogo con fotos redondas
- [ ] Pantallas de la dueña: inicio con portada, y el resto con los componentes nuevos
- [ ] Ajustes de T18: productos sin existencias plegados, resumen de insumos en columnas, producción reciente corta
- [ ] Uso de las fotos del contrato (las trae otro agente)
- [ ] Pruebas de marca y contraste actualizadas; capturas en `apps/web/e2e-artifacts/t21/`

## Criterios de aceptación
- Capturas a 390 y 1280 px de entrar, inicio, portal y tablero que se parecen a la referencia (panel oscuro diagonal,
  plato grande, título en dos pesos, píldoras amarillas/negras).
- Sin scroll horizontal; axe sin violaciones serias; `./scripts/check.sh` y las e2e de a11y, marca, plano, portal y
  visión pasan.

## Fuera de alcance
- Modo oscuro completo de la app.
- Cambiar textos o flujos (solo presentación), salvo los 3 ajustes de T18.

## Riesgos y preguntas abiertas
- Las fotos libres son genéricas (no de la pyme): se marcan como demo.
- Una estética muy de "landing" puede restar densidad en pantallas de trabajo: se aplica fuerte en entrar, inicio y
  portal, y sobria (tokens) en formularios y tablas.

## Resumen de cierre
(se completa al terminar)
