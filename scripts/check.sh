#!/usr/bin/env sh
# Corre todos los controles de calidad con el compose de desarrollo levantado.
set -eu
cd "$(dirname "$0")/.."
API="docker compose -f infra/docker-compose.yml exec -T api"
$API ruff check .
$API ruff format --check .
$API mypy app
$API pytest --cov --cov-report=term-missing:skip-covered "$@"
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web test
