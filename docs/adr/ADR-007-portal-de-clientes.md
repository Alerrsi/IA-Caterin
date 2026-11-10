# ADR-007 — Portal de clientes: el cliente final cotiza y envía su solicitud

- Estado: **aceptado** (10-nov-2026, pedido del usuario). Amplía el alcance de F3 (cotizador) y de T03 (roles).
- Contexto en: ADR-002 (cálculo determinista), T05 (cotizador), T03 (auth multi-tenant).

## Contexto

Hasta ahora solo la pyme cotizaba: la dueña pegaba el mensaje del cliente y armaba la cotización. El usuario pidió
"una interfaz web para el cliente que pueda cotizar pedidos de la misma forma que lo hace el dueño de la pyme".
Además, las cotizaciones deben quedar guardadas para el cliente, y el cliente debe poder enviarlas a la pyme, que
acepta la solicitud.

## Decisión

1. **Rol `customer`** en `app_user`: el cliente final tiene cuenta en la pyme (correo y contraseña, igual que el
   equipo) y entra por el mismo `/auth/login`.
   - Se registra con un **enlace de la pyme** (`#/cliente/<código>`, `pyme.customer_code`). La dueña lo crea, lo
     cambia o cierra el registro en Ajustes. El código anterior deja de servir; los clientes ya registrados siguen
     entrando.
   - Un correo pertenece a una sola pyme (el correo es único global, como el resto de las cuentas del MVP).
2. **Bloqueo central:** `get_current_user`, la dependencia de todas las rutas de la pyme, responde 403
   `staff_only` a un cliente. El portal usa sus propias dependencias (`CustomerDep`, `CustomerDB`). Una prueba
   recorre todas las rutas del OpenAPI con un token de cliente.
3. **Mismo motor de cotización** (`quotes.service.create_quote`, ADR-002) con el margen por defecto de la pyme.
   - El cliente solo ve el **precio al cliente**: productos, precio unitario, subtotal, neto, IVA, total y vigencia.
     Nunca costos, margen, insumos, proveedores ni stock (`portal/schemas.py`).
   - Si falta el precio de un insumo, el cliente **no ve montos** (serían menores al real): ve "precio por
     confirmar" y puede enviar igual. Lo mismo si la pyme no definió su margen.
   - El cliente elige entre las recetas activas marcadas como **producto final** (no las preparaciones base).
   - Puede escribir el pedido en texto libre: el mismo extractor con LLM, limitado a
     `PORTAL_EXTRACT_PER_HOUR` lecturas por cliente y hora (protege la CPU del servidor).
4. **Estados nuevos del pedido:**
   - `customer_draft`: cotizado y guardado por el cliente, **sin enviar**. La pyme no lo ve (ni en listas, ni por
     id, ni en el asistente).
   - `requested`: enviado; aparece a la dueña como "Solicitud de cliente".
   - La dueña **acepta** (`POST /orders/{id}/accept`): el pedido pasa a `confirmed` y su última cotización a
     `accepted`. Exige una cotización completa, para que el cliente vea el precio que se acepta. Antes puede
     recalcularla con sus precios y margen.
   - O **rechaza** (`POST /orders/{id}/reject`): el pedido pasa a `cancelled` y la cotización a `rejected`.
   - En ambos casos puede dejar un mensaje que el cliente ve (`owner_message`).
   - El cliente puede anular mientras la pyme no responde.
5. **Trazabilidad:** el pedido guarda `customer_user_id`, `submitted_at`, `decided_at` y `owner_message`. La
   cotización guarda, como siempre, precios, supuestos y quién la generó (el cliente o la dueña).

## El cliente elige la pyme (10-nov-2026, pedido del usuario)

- **Directorio:** el cliente ve las pymes con el portal abierto (más las que ya usa) y elige a cuál cotizar; los
  productos y precios son los de esa pyme. Se registra con el enlace de una pyme o eligiéndola del directorio
  (`GET /portal/directory`, público: solo nombre y comuna de las pymes que abrieron su portal).
- **Una cuenta por pyme con el mismo correo:** la primera vez que cotiza a una pyme se le crea una cuenta en ella
  (`app_user`, rol `customer`, misma contraseña). Así cada pedido sigue perteneciendo a una sola pyme y el
  aislamiento no cambia. El correo del equipo sigue siendo único en todo el sistema; el de un cliente es único por
  pyme (migración `7cd8acbbfff0`). Al entrar se usa su cuenta más antigua y "Mis cotizaciones" junta las de todas.
- **Escrituras:** el portal lee con una sesión sin tenant, filtrando siempre por las cuentas del cliente o por la pyme
  elegida, y escribe con una sesión de tenant de esa pyme.
- **Límite:** si el cliente cambiara su contraseña en una pyme, las demás cuentas no se enteran (hoy no hay cambio de
  contraseña para clientes).

## Consecuencias

- **Seguridad:** el riesgo principal es que un cliente vea datos internos. Se mitiga con el bloqueo central y con
  pruebas: el recorrido de todas las rutas, un cliente que no ve lo de otro cliente (404), una pyme que no ve las
  solicitudes de otra y respuestas sin costos ni nombres de insumos.
- **Datos personales:** se agregan nombre y correo del cliente final como cuenta. En el pedido se guardan como
  `customer_name` y `customer_contact`. Ver `SECURITY.md`.
- **Costo:** el registro es público con el enlace. Las lecturas con LLM tienen tope por cliente y hora. El tope vive
  en la memoria del proceso: alcanza para un servidor con un proceso (el despliegue del MVP); con varios procesos
  habría que moverlo a la base o a Redis.
- **Sin correo saliente:** el cliente ve la respuesta al volver a entrar. La dueña ve las solicitudes en Pedidos y
  un aviso en el inicio.
- **Migración:** al bajarla, los `customer_draft` pasan a `cancelled`, los `requested` a `draft` y las cuentas de
  clientes quedan desactivadas.

## Alternativas descartadas

- **Enlace sin cuenta** (cotizar con un enlace público): más simple, pero el cliente no podría ver sus cotizaciones
  guardadas en otro momento ni en otro equipo.
- **Que el cliente vea la cotización interna con los datos ocultos en la interfaz:** los datos viajarían igual en la
  respuesta de la API. Se usa un esquema propio, sin esos campos.
