# ADR-001 — Stack tecnológico

- Estado: aceptado (9-nov-2026)
- Contexto en: `AGENTS.md` sección 3

## Contexto

Cáterin es para emprendedoras de catering con márgenes ajustados, poco tiempo y a veces mala conectividad. El equipo es de tres estudiantes y tiene un semestre. El stack tiene que:

1. Costar poco de operar (un VPS pequeño, sin servicios de pago obligatorios).
2. Ser open source, con licencias permisivas.
3. Ser conocido por el equipo y tener buena documentación, para avanzar rápido con agentes de IA.
4. Servir para IA local (LLM, embeddings y visión) sin GPU en producción.

## Decisión

| Capa | Elección | Por qué |
|------|----------|---------|
| Backend | Python 3.12, FastAPI, Pydantic v2 | El ecosistema de IA (ONNX Runtime, LangChain, clientes de Ollama) es Python. FastAPI da validación tipada y OpenAPI sin esfuerzo extra |
| Base de datos | PostgreSQL 16 + pgvector | Una sola base para datos relacionales, vectores y búsqueda de texto completo (`spanish`). Evita mantener una base vectorial aparte |
| ORM y migraciones | SQLAlchemy 2.x + Alembic | Estándar, tipado, con migraciones reversibles |
| LLM y RAG | LangChain (solo para RAG y la abstracción del LLM), detrás de `LLMProvider` | Ahorra código de *loaders*, *splitters* y clientes; la interfaz propia permite reemplazarlo si estorba |
| Servidor de modelos | Ollama | Instalación simple, cuantización incluida, API HTTP local, caché de prefijo |
| Visión | RF-DETR + PyTorch para entrenar, ONNX Runtime para inferir | Licencia Apache 2.0 (Nano a Large) y exportación a ONNX para CPU (ADR-003) |
| Frontend | React + Vite + TypeScript, PWA, Tailwind | Una sola base de código para celular y escritorio, instalable, con soporte offline (ADR-004) |
| Infraestructura | Docker Compose en un VPS, Caddy | Despliegue reproducible con un comando; Caddy gestiona HTTPS automáticamente |
| Calidad | pytest, ruff, mypy, pre-commit, Vitest, Playwright, GitHub Actions | Estándar, gratis para repos públicos |

## Alternativas consideradas

- **App nativa (Android/iOS) o Expo:** mejor acceso a la cámara, pero hay que publicar en tiendas y mantener dos objetivos. Una PWA basta para la cámara (`<input capture>` / `getUserMedia`) y se actualiza sin tienda. Se reconsidera si la PWA no alcanza.
- **Django:** más baterías incluidas, pero FastAPI encaja mejor con *streaming* SSE y el tipado con Pydantic que usa el extractor.
- **Base vectorial dedicada (Qdrant, Chroma):** un servicio más que respaldar y mantener. Con pocas pymes, pgvector alcanza.
- **Supabase/Firebase:** reduce trabajo inicial, pero ata a un proveedor y su capa gratuita no cubre el LLM local.
- **APIs de LLM de pago como opción por defecto:** costo variable y envío de datos de clientes fuera del país. Quedan como opción por `.env` (ver SECURITY).

## Consecuencias

- Una sola base de datos que respaldar, lo que simplifica los backups (T11).
- La imagen de la API debe quedar liviana: **no se instala PyTorch en producción**. Los embeddings pasan por Ollama y la visión por ONNX Runtime (ADR-003).
- El equipo debe dominar dos lenguajes (Python y TypeScript).
- Si una elección resulta inviable, se escribe un ADR nuevo que reemplaza la fila correspondiente (regla de `AGENTS.md`).

## Observación sobre el entorno actual

El entorno virtual local (`env/`) usa **Python 3.13.5**, y el stack fija 3.12. Para el benchmark no importa, pero la API y el CI usan 3.12 (imagen `python:3.12-slim`). Se corrige en T01.
