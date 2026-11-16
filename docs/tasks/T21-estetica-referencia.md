# T21 — Rediseño de toda la app con la estética de la imagen de referencia
- Estado: hecha en la rama (16-nov-2026); falta integrar a `main` y mostrarla a personas reales
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

### Requisito: entrar sin scroll (pedido del usuario, 16-nov-2026)
La pantalla de entrar (y las de registro, que comparten el marco) no debe obligar a desplazarse: logo, título, correo,
contraseña, "Entrar", el mensaje de error y los dos enlaces caben en la primera vista.
- Celular: sin scroll vertical a 390×844 y a 360×640. El formulario manda: el panel es una franja de 18 % del alto
  (`clamp(88px, 18dvh, 200px)`) con el plato asomándose, recortado por la diagonal; en pantallas bajas (variante
  `short`, alto ≤ 780 px) se oculta el lema.
- Escritorio: sin scroll a 1280×800 y 1366×768 (formulario a un lado, panel al otro, todo en `100dvh`; en pantallas
  bajas el lema es más chico y se oculta el cupón).
- Se usa `min-h-dvh`, no `100vh` ni un alto fijo: con el teclado abierto o con zoom la página puede crecer y desplazarse,
  pero nunca recorta.
- Con zoom de texto al 125 % se permite desplazar (AA exige que el zoom funcione), sin recortar. Con el error visible
  tampoco hay scroll en 390×844, 1280×800 y 1366×768; en 360×640 con el error se permite desplazar, sin recortar.
- Registro: mismo marco en modo `compact` (sin lema en el celular). Tiene 4 o 5 campos, así que en un celular chico
  puede necesitar desplazarse; la prueba estricta es la de entrar.

## Entregables
- [x] ADR-013, skill `caterin-brand` y `.interface-design/system.md` al día
- [x] Tokens (`scripts/theme.mjs`), fuente, radios, sombras y patrón `doodles`
- [x] Componentes base (`ui.tsx`, `AppShell`, `Logo`, `charts.tsx`)
- [x] Entrar/registro con portada de plato grande
- [x] Portal: portada de la pyme casi como la imagen, directorio y catálogo con fotos redondas
- [x] Pantallas de la dueña: inicio con portada, y el resto con los componentes nuevos
- [x] Ajustes de T18: productos sin existencias plegados, resumen de insumos en columnas, producción reciente corta
- [x] Uso de las fotos del contrato (las trae otro agente)
- [x] Pruebas de marca y contraste actualizadas; capturas en `apps/web/e2e-artifacts/t21/`

## Criterios de aceptación
- `e2e/login-sin-scroll.e2e.ts`: `document.documentElement.scrollHeight <= window.innerHeight` y cada pieza (logo,
  correo, contraseña, "Entrar", enlaces) dentro de la ventana a 390×844, 360×640, 1280×800 y 1366×768; lo mismo con
  el error visible (salvo 360×640, donde nada se recorta); zoom al 125 % y teclado abierto sin recortes. Capturas en
  `apps/web/e2e-artifacts/t21/login-*.png`.
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
**Qué se hizo (16-nov-2026):**
- Paleta nueva declarada a mano en `scripts/theme.mjs` (tinta `#1a1a1a`, blanco, lienzo `#f7f6f3`, panel `#1b1b1b`,
  amarillo `#ffd45c` solo como fondo, ámbar `#7a5200` como acento de texto), con los mismos nombres de rol.
- Urbanist variable autoalojada (≈ 28 KB) en vez de IBM Plex (se quitaron sus 3 paquetes). Títulos en dos pesos.
- Forma: píldoras (`--radius-lg: 9999px`), tarjetas de 22 px, sombras difusas; patrón propio de dibujos de comida en
  SVG (`doodles`, `grid-paper`).
- Componentes: `Button` con `icon` (círculo amarillo), `IconDot`, `Pill`, `Page` con `lead`, `Cells` como tarjetas;
  `components/Food.tsx` (panel diagonal, plato, ingredientes flotando, cupón, garabato) con reemplazos dibujados
  cuando falta una foto.
- `AppShell`: barra superior en escritorio; barra inferior flotante oscura en el celular.
- Portadas al estilo de la referencia en entrar/registro, inicio de la dueña, portada de la pyme en el portal; portal
  con platos redondos; el resto de las pantallas toma la estética por tokens.
- Marca: logo recoloreado (tinta, vapor amarillo, esquina 120/512) y logotipo a trazos en Urbanist 800
  (`scripts/brand.py`), íconos de la PWA regenerados; colores de gráficos `#d99a00`/`#5a5ad6` validados con dataviz.
- Ajustes de T18: productos sin existencias plegados en "Sin existencias (N)", resumen de insumos en columnas,
  producción reciente con 5 y "Ver más", "Anular" discreto.
- Requisito "entrar sin scroll": cumplido y probado en 4 tamaños.
- Fotos: las trajo la tarea paralela (contrato `public/fotos/` y `photo_url`).

**Pruebas:** ver el informe de la tarea (Vitest, `check.sh`, e2e de a11y, estética, marca, portal, visión, tablero,
portada y entrar sin scroll). Capturas en `apps/web/e2e-artifacts/t21/` (no se versionan).

**Pendiente:**
- `THIRD_PARTY_NOTICES.md`: registrar Urbanist (OFL-1.1) y sacar IBM Plex; lo edita la tarea de las fotos.
- Mostrarla a una emprendedora real; revisar si el registro en un celular chico necesita algo más compacto.
- Integrar a `main` cuando el usuario lo apruebe.

**Riesgos:** la estética de landing resta densidad en pantallas de trabajo; se mantuvo sobria fuera de las portadas.
