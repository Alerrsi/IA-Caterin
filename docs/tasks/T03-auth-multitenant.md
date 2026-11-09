# T03 — Autenticación y multi-tenancy
- Estado: pendiente
- Depende de: T02
- Funcionalidad: transversal

## Objetivo
Que cada emprendedora entre con su cuenta, invite a su colaboradora y tenga la certeza de que nadie más ve los datos de su negocio.

## Contexto y decisiones previas
- Auth y roles: `docs/API.md`, sección 1. Reglas: `docs/SECURITY.md`, secciones 1 y 2. Tenancy: `docs/DATA_MODEL.md`, sección 4.
- JWT de acceso de 15 min y refresh rotado en una cookie `HttpOnly`.

## Entregables
- [ ] `POST /auth/register` (crea la pyme y la dueña), `login`, `refresh`, `logout`, `GET /auth/me`.
- [ ] Hash Argon2id; límite de intentos de login.
- [ ] `core/tenancy.py`: `get_current_user`, `get_tenant` y `TenantSession` con filtro automático por `pyme_id`.
- [ ] `require_role("owner")` como dependencia.
- [ ] `GET/PATCH /pyme`, `GET/POST /users`, `PATCH/DELETE /users/{id}` (solo dueña).
- [ ] Evaluar Row Level Security de Postgres: implementarlo o documentar por qué no en un ADR corto.
- [ ] Fixture de tests con dos pymes y un helper `assert_isolated(endpoint)` reutilizable por las tareas siguientes.
- [ ] Actualizar `docs/API.md` y `docs/SECURITY.md`.

## Criterios de aceptación
- Flujo completo con `curl` o tests: registrar → login → `/auth/me` → refresh → logout (el refresh revocado ya no sirve).
- Con un token de la pyme A, pedir cualquier recurso de B devuelve 404.
- Una colaboradora recibe 403 en las rutas solo para la dueña.
- Mensajes de error en español de Chile y en formato RFC 9457.

## Pruebas requeridas
- Unitarias: hash y verificación, emisión y validación de JWT (vencido, firma inválida, sin `pyme_id`).
- Integración: aislamiento A/B en todos los endpoints existentes; rotación y revocación de refresh; límite de intentos.

## Fuera de alcance
- Login social, recuperación de contraseña por correo (anotar en ROADMAP si se pide), varias pymes por usuaria.

## Riesgos y preguntas abiertas
- Recuperación de contraseña: sin correo saliente en el MVP, ¿basta con que la dueña restablezca la clave de la colaboradora?
- Confirmar la matriz de permisos de la colaboradora (pregunta 4 del índice).

## Resumen de cierre
(se completa al terminar)
