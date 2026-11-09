# ADR-006 — Row Level Security de Postgres: no en el MVP

- Estado: aceptado (9-nov-2026, T03)
- Contexto en: `docs/SECURITY.md`, sección 1; `docs/DATA_MODEL.md`, sección 4

## Contexto

T03 debía evaluar Row Level Security (RLS) como segunda barrera contra la fuga de datos entre pymes. Hoy hay tres barreras:

1. **Filtro central en la aplicación** (`app/core/tenancy.py`): un evento `do_orm_execute` agrega `pyme_id = :tenant` a todo SELECT, UPDATE y DELETE del ORM sobre tablas de negocio, y un `before_flush` asigna el `pyme_id` a los objetos nuevos y rechaza los de otra pyme (`TenantViolationError`).
2. **FK compuestas** `(pyme_id, x_id) → (pyme_id, id)`: la base rechaza referencias entre pymes aunque el código falle.
3. **Tests de aislamiento** con dos pymes en cada módulo (`tests/helpers.py::assert_isolated`).

## Decisión

**No activar RLS en el MVP.** Se reevalúa en T11 (endurecimiento de producción).

## Motivos

- RLS exige que la API se conecte con un rol **sin** `BYPASSRLS` ni dueño de las tablas, y que cada transacción haga `SET LOCAL app.pyme_id = …`. Eso obliga a separar el rol de migraciones del rol de la app y a cuidar el pool de conexiones: un `SET` que se escape a otra solicitud sería peor que no tener RLS.
- Las consultas que hoy necesitan saltarse el filtro a propósito (login, unicidad global del correo, revocar tokens) tendrían que pasar a funciones `SECURITY DEFINER`.
- Con las tres barreras actuales y un solo servicio que escribe en la base, el beneficio marginal no compensa la complejidad para un equipo de tres personas en un semestre.

## Riesgos que quedan

- **SQL textual** (`text("...")`) o `Core` sin pasar por el ORM **no** recibe el filtro automático. Regla: los módulos de negocio no usan SQL textual; si alguna vez hace falta, se agrega `pyme_id` explícito y un test de aislamiento.
- `execution_options(skip_tenant_filter=True)` desactiva el filtro. Solo se permite en `modules/auth/service.py` y debe revisarse en code review.

## Consecuencias

- T11 decide si activar RLS al crear los roles de producción (`caterin_migrator` y `caterin_app`).
