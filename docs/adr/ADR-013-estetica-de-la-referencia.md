# ADR-013 — Estética de la imagen de referencia en toda la app

- Estado: aceptado (16-nov-2026, T21)
- Reemplaza a: [ADR-008](ADR-008-identidad-visual.md) (color laurel y cobre) y [ADR-010](ADR-010-estetica-plano.md)
  (estética "plano de cocina"). El logo de la cloche de ADR-008 se mantiene, recoloreado.
- Tarea: [T21](../tasks/T21-estetica-referencia.md)

## Contexto
El 16-nov-2026 el usuario pasó una imagen de referencia (landing de comida: título grande en dos pesos, plato redondo
enorme sobre un panel casi negro con corte diagonal y dibujos de comida en línea fina, ingredientes flotando, botones
en píldora con un círculo amarillo, tarjeta punteada tipo cupón). T19 la aplicó solo a la portada del portal y dentro
de la marca laurel; el usuario respondió "yo no veo el diseño como el de la foto" y eligió: **toda la app**, **muy
fiel a la imagen** y **fotos de comida de licencia libre** para la demo.

## Decisión
Se toman los rasgos visuales de la referencia como identidad de Cáterin, sin su marca (ni logo, ni nombre, ni textos):

| Rasgo | Valor |
|-------|-------|
| Fondo | Blanco `#ffffff`; lienzo `#f7f6f3` |
| Tinta y botón principal | Casi negro `#1a1a1a` con texto blanco |
| Panel oscuro | `#1b1b1b` con corte diagonal y patrón de dibujos de comida en línea fina (SVG propio, `doodles`) |
| Acento | Amarillo cálido `#ffd45c` solo como **fondo** (círculo del ícono del botón, chips, detalles); el texto sobre él es negro. Nunca amarillo como texto sobre blanco (1,4:1) |
| Acento de texto | Ámbar oscuro `#7a5200` para íconos o detalles sobre blanco (AA) |
| Tipografía | Urbanist variable (OFL-1.1, `@fontsource-variable/urbanist`, autoalojada): títulos en dos pesos (400 arriba, 800 abajo), interfaz en 500. Reemplaza IBM Plex. Las cifras usan la misma fuente con cifras tabulares |
| Forma | Botones y navegación en píldora; tarjetas de 20–28 px; campos de 14 px |
| Profundidad | Sombras suaves y difusas (`shadow-soft`, `shadow-key`) |
| Fotos | Platos redondos vistos desde arriba, recortados en círculo, que se salen del panel; ingredientes flotando con sombra |

Los tokens ya no salen de una semilla MD3: `scripts/theme.mjs` declara la paleta a mano (mismos nombres de roles,
para no tocar cada componente) y `src/theme.test.ts` sigue verificando AA en cada par.

## Consecuencias
- Cambian todas las pantallas a través de tokens y componentes base; las pantallas clave (entrar, inicio, portal)
  tienen además una portada con plato grande.
- Pruebas de marca (`brand.test.tsx`, `plano.test.tsx`, e2e de marca y plano) se actualizan a las reglas nuevas.
- Fuentes: Urbanist latino variable ≈ 28 KB, menos que las tres IBM Plex.
- Las fotos de la demo son de licencia libre y quedan registradas en `THIRD_PARTY_NOTICES.md` (las trae una tarea
  aparte dentro de T21); no representan productos reales de una pyme. Sin foto, cada pantalla usa un vacío dibujado.
- Riesgo: el amarillo de bajo contraste tienta a usarlo como texto; la regla y la prueba de contraste lo impiden.
