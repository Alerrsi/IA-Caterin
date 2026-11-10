# T13 — Portal de clientes
- Estado: hecha (10-nov-2026)
- Depende de: T03, T05, T08
- Funcionalidad: F3

## Objetivo
Que el cliente final cotice solo su pedido con los precios de la pyme, guarde sus cotizaciones y se las envíe a la
dueña, que las acepta o rechaza sin volver a escribir el pedido.

## Contexto y decisiones previas
ADR-007 (pedido del usuario del 10-nov-2026). Mismo motor de cotización que la dueña (ADR-002).

## Entregables
- [x] Rol `customer`, estados `customer_draft` y `requested`, columnas del pedido y `pyme.customer_code` (migración
  `e161a90baaa3`, sube y baja).
- [x] Bloqueo central de las rutas de la pyme para clientes (`get_current_user` → 403 `staff_only`).
- [x] Módulo `apps/api/app/modules/portal`: registro con el enlace, productos, leer pedido con LLM (con tope por hora),
  cotizar y guardar, recalcular, enviar, anular y PDF.
- [x] Dueña: `POST /orders/{id}/accept` y `/reject` con mensaje; enlace del portal en `POST/DELETE /pyme/customer-code`.
- [x] Web: registro `#/cliente/<código>`, "Mis cotizaciones", cotizar (misma pantalla que la dueña, en modo portal),
  detalle con enviar, PDF y anular; para la dueña, solicitudes en Pedidos, aviso en el inicio y enlace en Ajustes.
- [x] (10-nov) El cliente elige a qué pyme cotizar (directorio de pymes con portal abierto); una cuenta por pyme con
  el mismo correo; "Mis cotizaciones" junta todas. Registro también sin enlace, eligiendo del directorio.
- [x] (10-nov) Panel de la dueña: la lista de pedidos ya no corta las solicitudes ni los próximos (antes, con más de
  200 pedidos, quedaban fuera los más lejanos); la tarjeta muestra total cotizado, invitados y contacto.

## Criterios de aceptación
- Un cliente no entra a ninguna ruta de la pyme: `tests/test_portal.py::test_customer_cannot_use_any_staff_route`.
- Lo que el cliente no envió no lo ve la pyme. El cliente no ve costos, margen ni insumos.
- Un cliente no ve lo de otro cliente. Una pyme no ve las solicitudes de otra.
- Con un precio faltante, el cliente no ve montos y la dueña no puede aceptar sin una cotización completa.

## Pruebas requeridas
- API: `apps/api/tests/test_portal.py` (22 pruebas, incluidas las de varias pymes).
- Web: `apps/web/src/pages/portal/Portal.test.tsx` (8 pruebas).

## Fuera de alcance
- Correo o WhatsApp saliente para avisar al cliente de la respuesta.
- Pagos, abonos o firma de la cotización.
- Un mismo correo en varias pymes.

## Riesgos y preguntas abiertas
- El tope de lecturas con LLM vive en la memoria del proceso (ver ADR-007).
- Recuperación de contraseña del cliente: no hay correo saliente; hoy no tiene cómo recuperarla.
- Validar con una emprendedora real si quiere publicar sus precios en línea (el portal usa su margen por defecto).

## Resumen de cierre
Portal funcionando de punta a punta con pruebas de API y de interfaz. Sin prueba e2e con navegador (Playwright) ni
prueba con clientes reales.
