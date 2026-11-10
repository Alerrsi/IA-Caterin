# Cáterin

Software de gestión con IA para pymes de catering de La Araucanía (Chile).

> Proyecto de la asignatura Innovación y Emprendimiento III, INACAP Sede Temuco.
> Equipo: Víctor Rubilar, Alexis Salazar, Maximiliano González.

## Problema

**Pregunta de desafío:** ¿Cómo podríamos implementar IA para la automatización de los procesos de negocio, enfocados en las pymes del rubro de catering, con el objetivo de reducir tiempos en tareas complejas como manejo de finanzas, manejo de inventarios y comunicación con los clientes en la región de La Araucanía?

Las emprendedoras de catering hacen producción, compras, administración y atención a clientes al mismo tiempo. Hoy llevan finanzas e inventario en planillas Excel (lento y propenso a errores), y las soluciones existentes (Winnow, MarketMan, Toteat) son caras, pensadas para restaurantes de operación fija y no para catering por eventos.

**Propuesta de valor:** devolverle tiempo y tranquilidad a la emprendedora, automatizando lo repetitivo y dejando en sus manos las decisiones que requieren criterio humano.

## Las 3 funcionalidades del MVP

Surgen de las ideas elegidas en el brainstorming (Figura 1, cuadrante factible + original).

| # | Funcionalidad | Qué hace | Stack principal |
|---|---------------|----------|-----------------|
| 1 | **Asistente de gestión** | Responde en lenguaje natural sobre el estado de la pyme: inventario, costos, pedidos, finanzas. Funciona por niveles: lo determinista primero (consultas y plantillas, sin LLM) y un LLM pequeño solo para redactar o para preguntas abiertas sobre documentos | Enrutador de intenciones (reglas + `bge-m3`), pgvector, LangChain (RAG), LLM pequeño con Ollama |
| 2 | **Computer Vision desde el celular** | Reconoce y cuenta los productos finales de la producción a partir de una foto | PyTorch, ONNX Runtime |
| 3 | **Cotización automatizada de materias primas** | A partir de un pedido, calcula insumos necesarios y compara precios de proveedores | FastAPI, motor determinista + LLM solo para extraer/normalizar |

## Atributos de diseño (Panel de Metáfora)

Metáfora: *"El empresario debe informarse como un general de guerra"*.

- **Ágil:** menos tareas repetitivas, pocos clics.
- **Centralizado:** un solo lugar para finanzas, inventario y pedidos.
- **Accesible:** bajo costo, open source, fácil de alojar y mantener, usable desde el celular y con conectividad limitada.
- **Preciso:** cálculos consistentes y trazables, sin errores de planilla.

## Arquitectura (resumen)

```
┌──────────────────────┐        ┌───────────────────────────────┐
│  PWA React (móvil)   │ HTTPS  │  API FastAPI                  │
│  cámara · chat · UI  │◄──────►│  auth · inventario · recetas  │
└──────────────────────┘        │  cotizador · visión · asistente│
                                └──────┬───────────┬────────────┘
                                       │           │
                      ┌────────────────▼──┐   ┌────▼─────────────┐
                      │ PostgreSQL        │   │ Ollama (LLM +    │
                      │ + pgvector (RAG)  │   │ embeddings, local)│
                      └───────────────────┘   └──────────────────┘
                                       │
                              ┌────────▼─────────┐
                              │ ONNX Runtime (CV)│
                              └──────────────────┘
```

Detalle en `docs/ARCHITECTURE.md` y decisiones en `docs/adr/`.

## Estructura del repositorio

```
caterin/
├── AGENTS.md                # Instrucciones para agentes de IA (leer primero)
├── README.md
├── apps/
│   ├── api/                 # FastAPI (Python 3.12)
│   │   ├── app/
│   │   │   ├── core/        # config, seguridad, logging
│   │   │   ├── db/          # modelos SQLAlchemy, migraciones Alembic
│   │   │   ├── modules/
│   │   │   │   ├── auth/
│   │   │   │   ├── inventory/
│   │   │   │   ├── recipes/
│   │   │   │   ├── quotes/       # funcionalidad 3
│   │   │   │   ├── vision/       # funcionalidad 2
│   │   │   │   ├── assistant/    # funcionalidad 1
│   │   │   │   └── metrics/
│   │   │   └── main.py
│   │   └── tests/
│   └── web/                 # React + Vite + TypeScript (PWA)
├── ml/
│   ├── bench/               # benchmark en CPU de los modelos (bench_cpu.py)
│   ├── vision/              # entrenamiento PyTorch, export ONNX, model card
│   └── evals/               # evaluación del RAG y del extractor de pedidos
├── infra/                   # docker-compose, Dockerfiles, Caddy
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── API.md
│   ├── adr/                 # Architecture Decision Records
│   └── tasks/               # documentos de tareas (los crea el agente)
└── .env.example
```

## Puesta en marcha

Requisitos: Docker con Docker Compose y unos 10 GB libres de disco (imágenes y modelos). El LLM por defecto es pequeño (`qwen3:4b`); en pruebas con un notebook i5 de 8.ª gen y 16 GB de RAM, sin GPU, funcionó en CPU. También se puede configurar un proveedor externo en `.env`.

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d --build
# Descargar el modelo local (una sola vez, ~2.5 GB)
docker compose -f infra/docker-compose.yml exec ollama ollama pull qwen3:4b   # ver AGENTS.md sección 3.1
# Migraciones y datos de ejemplo (sintéticos)
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
docker compose -f infra/docker-compose.yml exec api python -m app.db.seed
# Opcional: pyme de demo GRANDE que llena todas las tablas (~1,5 min; necesita Ollama con bge-m3)
docker compose -f infra/docker-compose.yml exec api python -m app.db.demo_full
```

**Cuentas de demo** (todas con la contraseña `caterin-demo-2026`, datos sintéticos):

| Pyme | Cuentas | Para qué |
|------|---------|----------|
| Cocina Los Aromos (`seed`) | `duena.aromos@demo.local`, `colaboradora.aromos@demo.local` | Datos chicos y fijos: los usan las pruebas y los sets de evaluación. No modificarlos a mano |
| Banquetería del Lago (`seed`) | `duena.lago@demo.local` | Segunda pyme para probar el aislamiento |
| Banquetería Volcán Llaima (`demo_full`) | `duena.llaima@demo.local`, `cocina.llaima@demo.local`, `ventas.llaima@demo.local`; clientes del portal `cliente1.llaima@demo.local` … `cliente8.llaima@demo.local` (enlace `#/cliente/llaima-demo-2026`) | Volumen para la demo: ~100 insumos, 10 proveedores con historial de precios, 30 recetas, ~220 pedidos en 8 meses con cotizaciones, más de 3.600 movimientos de stock, caja, producción, 6 documentos indexados, fichas del RAG, preguntas al asistente, métricas y solicitudes del portal |

- API: http://localhost:8000/docs (OpenAPI en `/api/v1/openapi.json`)
- Web: http://localhost:5173
- Postgres queda en `localhost:5433` (para no chocar con otro Postgres local).

Controles de calidad (con el compose levantado): `./scripts/check.sh`. Verificar los modelos: `python scripts/verify_models.py`.

Los comandos los mantiene el equipo en `docs/tasks/T01-fundaciones.md`; si algo de este README no corre, es un bug y debe corregirse.

## Métricas de éxito

1. **Satisfacción:** encuesta de 1 a 5 estrellas dentro de la app.
2. **Tiempo de cotización:** minutos por cotización antes (manual) vs. después (Cáterin).
3. **Tiempo de respuesta del asistente:** segundos del asistente vs. tiempo medido de buscar el dato a mano.

El tiempo "antes" se cronometra con `docs/metrics/protocolo-cotizacion-manual.md`. La dueña ve el panel en **Mis métricas** (con n, periodo y descarga CSV); el equipo puede sumar todas las pymes con `python -m app.modules.metrics.report --exclude-demo`.

## Desarrollo con agentes

Este repo está pensado para trabajarse con agentes de IA. Antes de tocar código, el agente debe leer `AGENTS.md` y el documento de tarea correspondiente en `docs/tasks/`. Los commits siguen Conventional Commits y referencian el ID de tarea.

## Licencia

Por definir por el equipo. Dependencias: preferir licencias permisivas (MIT, Apache-2.0, BSD).
