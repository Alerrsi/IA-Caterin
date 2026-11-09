# T03 — Autenticación y multi-tenancy
- Estado: hecha
- Depende de: T02
- Funcionalidad: transversal

## Objetivo
Que cada emprendedora entre con su cuenta, invite a su colaboradora y tenga la certeza de que nadie más ve los datos de su negocio.

## Contexto y decisiones previas
- Auth y roles: `docs/API.md`, sección 1. Reglas: `docs/SECURITY.md`, secciones 1 y 2. Tenancy: `docs/DATA_MODEL.md`, sección 4.
- JWT de acceso de 15 min y refresh rotado en una cookie `HttpOnly`.

## Entregables
- [x] `POST /auth/register` (crea la pyme y la dueña), `login`, `refresh`, `logout`, `GET /auth/me`.
- [x] Hash Argon2id; límite de intentos de login.
- [x] `core/tenancy.py`: `get_current_user`, `get_tenant` y `TenantSession` con filtro automático por `pyme_id`.
- [x] `require_role("owner")` como dependencia.
- [x] `GET/PATCH /pyme`, `GET/POST /users`, `PATCH/DELETE /users/{id}` (solo dueña).
- [x] Evaluar Row Level Security de Postgres: implementarlo o documentar por qué no en un ADR corto.
- [x] Fixture de tests con dos pymes y un helper `assert_isolated(endpoint)` reutilizable por las tareas siguientes.
- [x] Actualizar `docs/API.md` y `docs/SECURITY.md`.

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
**Qué se hizo (9-nov-2026):**
- `modules/auth` (registro, login, refresh rotado con detección de reutilización, logout, `/auth/me`, `/pyme`, `/users`).
- `core/tenancy.py`: `get_current_user` (valida JWT y que la usuaria siga activa), `get_tenant_db` con filtro automático por `pyme_id` en SELECT/UPDATE/DELETE del ORM y asignación/verificación de `pyme_id` y `created_by` al hacer flush; `require_owner`.
- Límite de intentos de login por correo e IP (`login_attempt`).
- RLS evaluado y no activado: ADR-006.
- Helpers de prueba `register`, `login`, `assert_isolated` en `tests/helpers.py`.

**Verificado:** 46 pruebas pasan (11 nuevas de auth: flujo completo, correo duplicado, contraseña débil, mensaje genérico y 429, rotación y reutilización de refresh, logout, 6 tipos de token inválido, permisos de colaboradora, protección de la última dueña, usuaria desactivada pierde acceso, aislamiento A/B de `/users`, sesión de tenant que filtra lecturas y bloquea escrituras ajenas). ruff y `mypy --strict` limpios. Prueba manual con `curl` y las cuentas de demo: login correcto y `PATCH` a una usuaria de otra pyme → 404.

**Pendiente / riesgos:**
- Recuperación de contraseña por correo: fuera del MVP (la dueña restablece la de su colaboradora).
- La lista de contraseñas comunes es corta.
- El JWT de acceso no se puede revocar antes de sus 15 minutos (solo el refresh); al desactivar una usuaria, `get_current_user` revisa la base en cada solicitud, así que pierde el acceso de inmediato.
