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
| Pillow (fotos de visión y del catálogo del portal) | MIT-CMU (HPND) |
| python-multipart | Apache-2.0 |
| psycopg 3 | **LGPL-3.0**: se usa como biblioteca sin modificarla, lo que la LGPL permite en proyectos con otra licencia |

## Dependencias de la web (JavaScript)

| Paquete | Licencia |
|---------|----------|
| React, React DOM, React Router, Vite, Tailwind CSS, vite-plugin-pwa, Workbox, Vitest, Testing Library, ESLint, typescript-eslint | MIT |
| `@axe-core/playwright` y `axe-core` (solo pruebas de accesibilidad; no se distribuyen con la app) | MPL-2.0 |
| TypeScript | Apache-2.0 |
| Urbanist (`@fontsource-variable/urbanist` 5.3.0), fuente de la app y del logotipo (T21, ADR-013; antes IBM Plex, Roboto y Bricolage Grotesque) | OFL-1.1 (SIL Open Font License) |
| Íconos de Material Icons (trazos SVG copiados en `components/Icon.tsx`) | Apache-2.0 (Google) |
| `@material/material-color-utilities` (solo genera el tema con `npm run theme`; no se distribuye) | Apache-2.0 |
| Playwright (pruebas y generación de los PNG de la marca; no se distribuye) | Apache-2.0 |

## Skills de diseño para agentes (`.claude/skills/`, no se distribuyen con la app)

| Skill | Licencia | Origen |
|-------|----------|--------|
| `interface-design` (skill y comandos `/interface-design:*`) | MIT (Damola Akinleye) | github.com/Dammyjay93/interface-design, commit en `.claude/skills/SOURCES.md` |
| `web-interface-guidelines` | MIT (Vercel Labs) | github.com/vercel-labs/web-interface-guidelines, commit en `.claude/skills/SOURCES.md` |
| `emil-design-eng` | MIT (Emil Kowalski) | github.com/emilkowalski/skill, commit en `.claude/skills/SOURCES.md` |
| `frontend-design` | Apache-2.0 (Anthropic) | github.com/anthropics/skills, commit en `.claude/skills/SOURCES.md` |

## Datos de prueba de visión (no van a producción)

| Dato | Licencia | Notas |
|------|----------|-------|
| Snacks (Detection), cajas: huggingface.co/datasets/Matthijs/snacks-detection | CC BY 4.0 (anotaciones de Google, Open Images) | Solo clases cookie, muffin, doughnut y pretzel |
| Snacks, imágenes: huggingface.co/datasets/Matthijs/snacks | CC BY 2.0 (fotos de Flickr de distintos autores) | Atribución por foto en `ml/vision/data/raw/CREDITS.csv` (se genera con `prepare_snacks.py`; las fotos no se commitean). Un modelo entrenado solo con esto sirve para validar el pipeline, no como producto |

## Fotos de comida (T21)

Fotos de licencia libre descargadas el 16-nov-2026. **Pexels License** (pexels.com/license): uso gratuito, también comercial, se pueden modificar y no exige atribución; no se pueden vender copias sin cambios ni usarlas como marca o insinuar que una persona o marca respalda el producto. **CC0** y **dominio público** (Wikimedia Commons): sin restricciones. Igual se acredita a cada autor.

Cambios comunes a todas: redimensionadas (máx. 800 px las de producto, 900 px los platos, 300 px los ingredientes) y re-codificadas a WebP sin metadatos.

### Productos de la pyme de demo (`apps/api/app/db/demo_photos/`)

Se asignan a las recetas de «Banquetería Volcán Llaima (demo)» con `python -m app.db.demo_media`. Sin foto libre razonable: *Mote con huesillo*, *Sándwich de ave pimentón* y *Choripanes de cóctel* (este último no se muestra en el catálogo).

| Archivo | Autor | Licencia | Origen | Cambios |
|---------|-------|----------|--------|---------|
| `empanadas-de-pino.webp` | Daniel Torobekov | Pexels | https://www.pexels.com/photo/13689920/ | — |
| `empanadas-de-queso.webp` | pedro furtado | Pexels | https://www.pexels.com/photo/28902906/ | — |
| `empanadas-napolitanas.webp` | Los Muertos Crew | Pexels | https://www.pexels.com/photo/8279711/ | — |
| `empanadas-de-camaron-queso.webp` | Mary Locuaz | Pexels | https://www.pexels.com/photo/6535195/ | — |
| `sopaipillas.webp` | Warko2006 | Dominio público | https://commons.wikimedia.org/wiki/File:Sopaipillas_chilenas.jpg | — |
| `canapes-de-salmon.webp` | Matthew Osier | Pexels | https://www.pexels.com/photo/9524169/ | — |
| `canapes-de-ave-palta.webp` | Daniel Duarte | Pexels | https://www.pexels.com/photo/20807883/ | — |
| `canapes-de-queso-de-cabra-y-murta.webp` | Nadin Sh | Pexels | https://www.pexels.com/photo/16594947/ | — |
| `brochetas-de-pollo.webp` | Agung Pandit Wiguna | Pexels | https://www.pexels.com/photo/5407359/ | — |
| `brochetas-caprese.webp` | Amar Preciado | Pexels | https://www.pexels.com/photo/22820141/ | — |
| `brochetas-de-fruta.webp` | Vidal Balielo Jr. | Pexels | https://www.pexels.com/photo/4006858/ | — |
| `mini-quiches.webp` | Jonathan Borba | Pexels | https://www.pexels.com/photo/25916399/ | — |
| `sandwich-de-ave-mayo.webp` | Büşra Yurt | Pexels | https://www.pexels.com/photo/31742775/ | recortada (sin la ensalada de abajo) |
| `sandwich-de-jamon-queso.webp` | Marcelo Verfe | Pexels | https://www.pexels.com/photo/18784887/ | — |
| `mini-hamburguesas.webp` | Vidal Balielo Jr. | Pexels | https://www.pexels.com/photo/18354206/ | — |
| `tapaditos-de-salmon-fresco.webp` | Nikita Nikitin | Pexels | https://www.pexels.com/photo/8148261/ | — |
| `pie-de-limon.webp` | Valeria Boltneva | Pexels | https://www.pexels.com/photo/17283922/ | — |
| `kuchen-de-murta.webp` | Micheile Henderson | Pexels | https://www.pexels.com/photo/9588901/ | — |
| `kuchen-de-manzana.webp` | Ivanna Kykla | Pexels | https://www.pexels.com/photo/4018839/ | — |
| `torta-tres-leches.webp` | Muago | CC0 | https://commons.wikimedia.org/wiki/File:Torta_de_tres_leches_2.jpg | recortada (solo la torta, sin la botella de bebida de fondo) |
| `torta-de-chocolate-y-manjar.webp` | Marta Dzedyshko | Pexels | https://www.pexels.com/photo/7451890/ | — |
| `alfajores.webp` | Agustina R Street | Pexels | https://www.pexels.com/photo/17358380/ | — |
| `ensalada-chilena.webp` | Tamanna Rumee | Pexels | https://www.pexels.com/photo/7954630/ | — |
| `pastel-de-choclo-individual.webp` | mariela morales (Flickr, Marieloreto) | CC0 | https://commons.wikimedia.org/wiki/File:Pastel_de_choclo_-_Flickr_-_Marieloreto.jpg | — |
| `ceviche-de-reineta.webp` | Nano Erdozain | Pexels | https://www.pexels.com/photo/31495668/ | — |

### Decorativas de la web (`apps/web/public/fotos/`)

| Archivo | Autor | Licencia | Origen | Cambios |
|---------|-------|----------|--------|---------|
| `plato-hero.webp` | pedro furtado | Pexels | https://www.pexels.com/photo/28902906/ | recorte circular con fondo transparente |
| `plato-2.webp` | Olena Bohovyk | Pexels | https://www.pexels.com/photo/3743537/ | recorte circular del bol con fondo transparente |
| `plato-3.webp` | Micheile Henderson | Pexels | https://www.pexels.com/photo/8366817/ | recorte circular del plato con fondo transparente |
| `ingrediente-limon.webp` | Lukas Blazek | Pexels | https://www.pexels.com/photo/1414110/ | media mitad recortada en círculo, fondo transparente |
| `ingrediente-tomate.webp` | Tajana R | Pexels | https://www.pexels.com/photo/28971157/ | un tomate recortado, fondo quitado |
| `ingrediente-aji.webp` | Karola G (kaboompics.com) | Pexels | https://www.pexels.com/photo/4084633/ | un ají recortado, fondo quitado |
| `ingrediente-albahaca.webp` | Ruby Sengar | Pexels | https://www.pexels.com/photo/5498004/ | una hoja recortada, fondo quitado. Es una hoja de menta (la foto no tiene albahaca); se usa como hoja verde decorativa |
