# T01 — Fundaciones del repositorio
- Estado: hecha
- Depende de: —
- Funcionalidad: transversal

## Objetivo
Dejar un repositorio que cualquiera del equipo levante con un par de comandos, con controles de calidad automáticos, para que el resto de las tareas avance rápido y sin romper lo anterior.

## Contexto y decisiones previas
- Stack: ADR-001. Estructura de carpetas: `README.md`. Límites de módulos: `docs/ARCHITECTURE.md`, sección 4.
- Supuesto: el monorepo no usa herramientas de workspace complejas; `apps/api` (Python con `uv` o `pip-tools`) y `apps/web` (npm o pnpm) tienen cada uno su gestor. El equipo elige `uv` o `pip-tools` al empezar y lo anota aquí.
- Supuesto: la rama principal es `main` (el repo hoy está en `master` sin commits; confirmar con el equipo antes de renombrar).

## Entregables
- [x] Estructura de carpetas del README (`apps/api`, `apps/web`, `ml/`, `infra/`, `docs/`) con `apps/api/app/modules/suppliers` (ARCHITECTURE).
- [x] Mover `main.py` → `ml/bench/bench_cpu.py`, y `requirements.txt` → `ml/bench/requirements.txt`. Actualizar las rutas en `AGENTS.md` y ADR-003.
- [x] `.gitignore`: `.env`, `env/`, `.venv/`, `node_modules/`, `output/`, `*.onnx`, `*.pt`, `*.safetensors`, datos de `ml/vision/data/`, dumps.
- [x] `apps/api`: FastAPI mínimo con `GET /api/v1/health/live` y `GET /api/v1/health/ready` (Postgres y Ollama), configuración con `pydantic-settings`, logging JSON y un manejador de errores RFC 9457.
- [x] `apps/web`: Vite + React + TypeScript + Tailwind + `vite-plugin-pwa`, con una página que llama a `/health/live`, y el archivo i18n `es-CL`.
- [x] `infra/docker-compose.yml` (desarrollo): `api`, `web`, `postgres` (`pgvector/pgvector:pg16`), `ollama`, con healthchecks y volúmenes con nombre.
- [x] Dockerfile de la API sobre `python:3.12-slim`, sin root y **sin PyTorch**.
- [x] `.env.example` con todas las variables y comentarios (sin secretos reales).
- [x] `pre-commit`: ruff (lint y formato), eslint en web, detector de secretos (gitleaks). **Cambio:** `mypy --strict` no va en pre-commit (necesita el entorno completo de la API); corre en CI y en `scripts/check.sh`. Prettier no se agregó.
- [x] GitHub Actions: lint, tipos y tests de API y web, build de la web y gitleaks.
- [ ] Build de las imágenes Docker en CI → queda para T11 (compose de producción).
- [x] `models.lock.yaml` inicial (qwen3:4b, bge-m3, RF-DETR Nano) y `scripts/verify_models.py`, que comprueba el sha256 de los ONNX y que los tags de Ollama existan.
- [x] Verificar las licencias de la tabla de ADR-003 en las model cards oficiales y crear `THIRD_PARTY_NOTICES.md`.
- [x] Corregir los comandos de puesta en marcha del README para que coincidan con lo que de verdad funciona (p. ej. `docker compose -f infra/docker-compose.yml exec ...`).

## Criterios de aceptación
- En una máquina limpia, con Docker: `cp .env.example .env && docker compose -f infra/docker-compose.yml up -d` deja todos los servicios en estado `healthy` en menos de 5 minutos (sin contar la descarga de modelos).
- `curl localhost:8000/api/v1/health/ready` devuelve 200 con el estado de cada componente.
- `http://localhost:5173` muestra la página inicial y la PWA es instalable (Lighthouse: "installable").
- `pre-commit run --all-files` pasa. El CI pasa en verde en un PR.
- `python scripts/verify_models.py` pasa (o falla con un mensaje claro si falta un modelo).
- `git status` no muestra el ONNX ni el entorno virtual.

## Pruebas requeridas
- Unitarias: configuración (valores por defecto, variables faltantes), formato de error RFC 9457.
- Integración: `/health/ready` con Postgres arriba y abajo.

## Fuera de alcance
- Modelos de datos (T02), autenticación (T03), despliegue de producción (T11).

## Riesgos y preguntas abiertas
- La imagen de Ollama y los modelos pesan varios GB; documentar el espacio en disco necesario.
- Si alguien del equipo usa Windows, verificar Docker Desktop y los finales de línea (`.gitattributes`).
- ¿`uv` o `pip-tools`? ¿npm o pnpm?

## Resumen de cierre
**Qué se hizo (9-nov-2026):**
- Monorepo con `apps/api` (FastAPI, Python 3.12 en Docker), `apps/web` (Vite + React 19 + TypeScript 6 + Tailwind 4 + PWA), `ml/bench`, `infra`, `scripts`.
- Rama principal renombrada de `master` a `main` (sin commits previos). Por pedido del usuario se trabaja directo en `main`, no en ramas `feat/Txx`.
- Gestores elegidos: `pip` con `requirements*.txt` fijados (API) y `npm` con `package-lock.json` (web).
- `/health/ready` informa base de datos (obligatoria, 503 si cae) y LLM (opcional: `degraded` si falta, porque F3 tiene formulario manual de respaldo).
- Compose de desarrollo con `postgres` (pgvector, puerto host 5433), `ollama` (sin puerto publicado), `api` (recarga en caliente) y `web`. El init de Postgres crea `caterin_test` y las extensiones `vector` y `citext`.
- Licencias verificadas en los metadatos de las model cards (ADR-003, `THIRD_PARTY_NOTICES.md`). Corrección: RF-DETR Atto/Femto/Pico también son PML 1.0.
- `models.lock.yaml` + `scripts/verify_models.py` (digest de Ollama, sha256 del ONNX).
- `AGENTS.md` actualizado: rutas de `ml/bench/` y aclarado que el bug de RAM **sigue presente** en el script.

**Verificado:** `docker compose up -d --build` deja todo `healthy`; `/health/ready` = ok con `qwen3:4b`; ruff, `mypy --strict` y 8 tests de la API pasan en el contenedor; lint, typecheck, 2 tests y build de la web pasan; `pre-commit run --all-files` pasa; `verify_models.py` pasa.

**Pendiente / riesgos:**
- **El CI de GitHub Actions no se ha ejecutado**: el repo no tiene remoto. Se validará en el primer push.
- Lighthouse "installable" no se midió con Lighthouse; el build genera el manifiesto y el service worker.
- El entorno local `env/` sigue en Python 3.13 (solo se usa para el benchmark y pre-commit); la API corre en 3.12 dentro de Docker.
- Las imágenes de Ollama y los modelos ocupan varios GB.
