# Avisos de terceros — Cáterin

Licencias de los modelos y dependencias principales. Revisado el 9-nov-2026. Las versiones exactas están en `models.lock.yaml`, `apps/api/requirements*.txt` y `apps/web/package-lock.json`.

## Modelos de IA

| Modelo | Uso | Licencia | Cómo se verificó |
|--------|-----|----------|------------------|
| Qwen3 4B (`qwen3:4b`) | LLM por defecto | Apache-2.0 | Metadatos de la model card `Qwen/Qwen3-4B` (API de Hugging Face) |
| Qwen3 8B (`qwen3:8b`) | LLM nivel 3, opcional | Apache-2.0 | Metadatos de la model card `Qwen/Qwen3-8B` |
| Gemma 4 E4B (`gemma4:e4b`) | Candidato a evaluar | Apache-2.0 | Metadatos de la model card `google/gemma-4-E4B-it` |
| BGE-M3 | Embeddings | MIT | Metadatos de la model card `BAAI/bge-m3` |
| BGE Reranker v2 M3 | Reranker, opcional | Apache-2.0 | Metadatos de la model card `BAAI/bge-reranker-v2-m3` |
| Qwen3-Embedding-0.6B | Candidato a evaluar | Apache-2.0 | Metadatos de la model card |
| RF-DETR Nano/Small (paquete `rfdetr`) | Detector | Apache-2.0 | `LICENSE` y README del repo `roboflow/rf-detr`. Los tamaños Atto, Femto, Pico, XL y 2XL (`rfdetr[plus]`) son PML 1.0 y **no se usan** |

## Software de infraestructura

| Componente | Licencia |
|------------|----------|
| PostgreSQL | PostgreSQL License |
| pgvector | PostgreSQL License |
| `unaccent` (contrib de PostgreSQL, búsqueda sin tildes) | PostgreSQL License |
| Ollama | MIT |
| Caddy (T11) | Apache-2.0 |

## Dependencias de la API (Python)

| Paquete | Licencia |
|---------|----------|
| FastAPI, Pydantic, pydantic-settings, SQLAlchemy, Alembic, pgvector (Python), argon2-cffi, PyJWT, openpyxl, RapidFuzz, PyYAML | MIT |
| Uvicorn, HTTPX, pypdf (lectura de PDF para el asistente) | BSD-3-Clause |
| ReportLab | BSD |
| python-multipart | Apache-2.0 |
| psycopg 3 | **LGPL-3.0**: se usa como biblioteca sin modificarla, lo que la LGPL permite en proyectos con otra licencia |

## Dependencias de la web (JavaScript)

| Paquete | Licencia |
|---------|----------|
| React, React DOM, React Router, Vite, Tailwind CSS, vite-plugin-pwa, Workbox, Vitest, Testing Library, ESLint, typescript-eslint | MIT |
| TypeScript | Apache-2.0 |

## Datos de prueba de visión (no van a producción)

| Dato | Licencia | Notas |
|------|----------|-------|
| Snacks (Detection), cajas: huggingface.co/datasets/Matthijs/snacks-detection | CC BY 4.0 (anotaciones de Google, Open Images) | Solo clases cookie, muffin, doughnut y pretzel |
| Snacks, imágenes: huggingface.co/datasets/Matthijs/snacks | CC BY 2.0 (fotos de Flickr de distintos autores) | Atribución por foto en `ml/vision/data/raw/CREDITS.csv` (se genera con `prepare_snacks.py`; las fotos no se commitean). Un modelo entrenado solo con esto sirve para validar el pipeline, no como producto |
