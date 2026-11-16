# T22 — Acceso rápido: todo a uno o dos toques
- Estado: pendiente (plan del 16-nov-2026; se implementa cuando termine T21, que está rehaciendo la navegación)
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
- [ ] Barra de 5 con "Más" y barra lateral agrupada
- [ ] Buscador global con acciones y datos, sin red
- [ ] Volver con historial y filtros en la URL
- [ ] Saltar al contenido, foco y anuncio al cambiar de pantalla, ayuda de atajos
- [ ] Inicio con acciones rápidas y "Seguir donde quedaste"
- [ ] Pruebas de alcance y de teclado; documentación e índice

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
(se completa al terminar)
