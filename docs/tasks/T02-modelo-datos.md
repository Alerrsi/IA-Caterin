# T02 — Modelo de datos, migraciones y seed
- Estado: hecha
- Depende de: T01
- Funcionalidad: transversal

## Objetivo
Tener una única fuente de verdad para insumos, recetas, pedidos, precios y producción, con datos de ejemplo de catering realistas para probar todo sin depender de una pyme real.

## Contexto y decisiones previas
- Entidades, tipos y reglas: `docs/DATA_MODEL.md`.
- Dinero en `numeric(12,0)` CLP, cantidades en `numeric(14,3)` en unidad base (ADR-002).
- Stock como libro de movimientos (ADR-004).
- Decisión pendiente: si `cash_movement` entra al MVP (pregunta 3 del índice). Si no se decide antes de empezar, se crea la tabla igual (es pequeña) y se marca como opcional en la interfaz.

## Entregables
- [x] Modelos SQLAlchemy 2.x tipados en `app/db/models/` para todas las entidades de DATA_MODEL.
- [x] Mixin común (`id`, `pyme_id`, `created_at`, `updated_at`, `created_by`) y FK compuestas `(pyme_id, id)`.
- [x] Extensiones `vector` y `citext` en la primera migración.
- [x] Migraciones Alembic desde cero, con `downgrade` en todas.
- [x] `document_chunk.embedding` como `vector(1024)` con índice HNSW (coseno) y `tsv` generado con `spanish` e índice GIN.
- [x] Índices: `pyme_id` en todas las tablas, únicos por pyme, parcial único de precio vigente.
- [x] `app/core/units.py`: unidades base y conversiones fijas, con tests.
- [x] `python -m app.db.seed`: **dos pymes de demo** (para probar el aislamiento) con ~30 insumos, ~8 recetas (empanadas de pino, canapés, brochetas, mini quiches, sopaipillas…), 3 proveedores con precios en CLP, 5 pedidos y movimientos de stock. Todo marcado como **sintético** (`name` con sufijo "(demo)" o un campo `is_demo`).
- [x] Actualizar `docs/DATA_MODEL.md` con cualquier cambio hecho al implementar.

## Criterios de aceptación
- `docker compose exec api alembic upgrade head` en una base vacía funciona; `alembic downgrade base` también, y volver a subir no falla.
- `docker compose exec api python -m app.db.seed` es idempotente (correrlo dos veces no duplica).
- `alembic check` (o `autogenerate` sin cambios) confirma que los modelos y las migraciones coinciden.
- Un test intenta crear una `recipe_line` de la pyme A apuntando a un insumo de la pyme B y la base lo rechaza.

## Pruebas requeridas
- Unitarias: conversiones de unidades (kg↔g, L↔ml, docena), rechazo de masa↔volumen sin densidad.
- Integración (Postgres real en Docker o testcontainers): migraciones arriba y abajo, restricciones únicas y FK compuestas.

## Fuera de alcance
- Endpoints (T03 en adelante). Lógica de costeo (T04).

## Riesgos y preguntas abiertas
- Los precios del seed deben parecer razonables, pero **no presentarse como precios reales de mercado**. Anotar en el seed la fecha y que son de demo.
- UUIDv7: confirmar que la librería elegida está mantenida; si no, usar v4.

## Resumen de cierre
**Qué se hizo (9-nov-2026):**
- Modelos en `app/db/models.py` (21 tablas), base con FK compuestas por tenant en `app/db/base.py`, enums en `app/db/enums.py`.
- Migración inicial `81b5e0e8e593` con extensiones, índice HNSW (coseno) y columna `tsv` generada con `spanish` + GIN.
- `app/core/units.py` (unidades base, conversiones, formato es-CL) y `app/core/money.py` (CLP, parseo de números chilenos como "21.000" y "2,5"), `app/core/security.py` (Argon2id).
- Seed idempotente con dos pymes sintéticas: "Cocina Los Aromos (demo)" (31 insumos, 3 proveedores, 8 recetas, 5 pedidos) y "Banquetería del Lago (demo)". Nombres, clientes y precios inventados; el eneldo queda sin precio a propósito.
- `DATA_MODEL.md` actualizado (sección 7).

**Verificado:** `alembic upgrade head`, `downgrade base` y otra vez `upgrade head` en el contenedor; `alembic check` sin diferencias; seed dos veces sin duplicar. 35 pruebas pasan (unidades, dinero con Hypothesis, migraciones, FK entre pymes rechazada por la base, nombres únicos por pyme, precio vigente único, CHECKs, seed). ruff y `mypy --strict` limpios.

**Pendiente / riesgos:**
- Contraseña de demo pública (`caterin-demo-2026`, configurable con `SEED_DEMO_PASSWORD`): las cuentas de demo **no deben existir en producción** (T11).
- Row Level Security no se activó (se evalúa en T03).
