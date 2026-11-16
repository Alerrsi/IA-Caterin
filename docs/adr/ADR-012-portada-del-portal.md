# ADR-012 — Portada de la pyme en el portal de clientes

- Estado: aceptado (16-nov-2026, T19). Su estética (panel laurel, marco punteado) la reemplaza [ADR-013](ADR-013-estetica-de-la-referencia.md) en T21; se mantienen la regla del destacado y del recomendado, y "sin precios".
- Relacionado: ADR-007 (portal), ADR-008 (identidad visual), ADR-009 (catálogo), ADR-010 (estética "plano de cocina")

## Contexto
El usuario pidió llevar al producto una tendencia de diseño web de comida: títulos e imágenes en gran tamaño, la foto
del plato sobre un panel oscuro con corte diagonal y una tarjeta punteada con un producto recomendado. ADR-010 dice que
en las pantallas de trabajo manda la claridad y que el único momento fuerte es el panel laurel rayado del login.

## Decisión
1. La **página de una pyme en el portal** (la vitrina que ve el cliente final) lleva una portada con:
   - el producto destacado en IBM Plex Serif grande, en dos tonos de texto (no dos pesos: no se agregan fuentes);
   - su foto grande en un marco punteado sobre un **panel laurel rayado** (`bg-brand hatch`) con corte diagonal por
     `clip-path`;
   - marcas pequeñas del plano (cuadrados finos y un punto cobre) como únicos adornos, sin animación;
   - el botón de la marca "Cotizar {producto}" y el bloque de la pyme (logo o inicial, nombre, comuna);
   - una tarjeta punteada "Recomendado" con un segundo producto.
2. Es una **excepción acotada** a "un solo momento fuerte": `brand` y `hatch` se permiten en el login y en esta portada,
   nunca en pantallas de trabajo de la pyme.
3. El destacado se elige con una regla determinista (primero con foto, luego con descripción, luego el primero). No se
   muestran precios (ADR-009): en su lugar, cómo se vende y "Precio al cotizar".

## Consecuencias
- La vitrina gana jerarquía sin cambiar la API ni las reglas de privacidad del portal.
- Sin fotos de productos la portada usa el vacío del plano (`grid-paper` + `cloche`); su fuerza depende de que las pymes
  suban al menos una foto.
- La skill `caterin-brand` registra la excepción.
