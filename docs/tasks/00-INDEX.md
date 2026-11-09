# Índice de tareas — Cáterin

Actualizado: 9-nov-2026. Por decisión del usuario (9-nov-2026), las tareas se trabajan directo en `main`, con un commit por tarea probada. El estado se marca aquí al cambiar.

| ID | Título | Funcionalidad | Estado | Depende de | Dueño |
|----|--------|---------------|--------|------------|-------|
| [T01](T01-fundaciones.md) | Fundaciones del repositorio | transversal | hecha | — | por asignar |
| [T02](T02-modelo-datos.md) | Modelo de datos, migraciones y seed | transversal | hecha | T01 | por asignar |
| [T03](T03-auth-multitenant.md) | Autenticación y multi-tenancy | transversal | hecha | T02 | por asignar |
| [T04](T04-inventario-recetas-proveedores.md) | Inventario, recetas, proveedores e importación | transversal | hecha | T03 | por asignar |
| [T05](T05-cotizador-f3.md) | Cotizador automatizado | F3 | hecha (API + pantallas) | T04 | por asignar |
| [T06](T06-vision-f2.md) | Conteo de productos por foto | F2 | en curso (API y datos listos; falta entrenar) | T04 | por asignar |
| [T07](T07-asistente-rag-f1.md) | Asistente por niveles con RAG | F1 | pendiente | T04 | por asignar |
| [T08](T08-frontend-pwa.md) | Frontend PWA mobile-first | transversal | en curso (F3 hecha) | T05, T06, T07 (por pantallas) | por asignar |
| [T09](T09-metricas.md) | Métricas de éxito | transversal | pendiente | T05, T07, T08 | por asignar |
| [T10](T10-calidad-evals.md) | Calidad y evaluaciones | transversal | pendiente | T05–T07 | por asignar |
| [T11](T11-despliegue.md) | Despliegue en producción | transversal | pendiente | T08 | por asignar |
| [T12](T12-documentacion-demo.md) | Documentación final y demo | transversal | pendiente | T09–T11 | por asignar |

Orden recomendado: T01 → T02 → T03 → T04 → (T05, T06, T07 en paralelo si hay capacidad) → T08 → T09 → T10 → T11 → T12.

T06 puede adelantar el trabajo de `ml/vision` (dataset, entrenamiento) en paralelo con T01–T04, porque no depende de la API.

## Estado del repositorio al crear este índice

- Hay un script de benchmark en `main.py` (es el `bench_cpu.py` que cita `AGENTS.md`), `requirements.txt` con sus dependencias, `bench_results.json` y `output/rfdetr-nano.onnx` (115 MB).
- Problemas detectados que ya están asignados a tareas:
  - `main.py` **no** tiene las correcciones que menciona `AGENTS.md` (RAM por prefijo, tokens generados, detalle de fallos) → T10. Ver ADR-003.
  - El ONNX de 115 MB y `env/` no deben entrar al repo → `.gitignore` en T01.
  - El entorno local usa Python 3.13.5 y el stack fija 3.12 → T01.

## Preguntas abiertas para el equipo

1. ¿Quién es dueño de cada tarea?
2. ¿Existe una versión corregida de `bench_cpu.py` en otro equipo? (ADR-003)
3. ¿Entra al MVP un registro mínimo de caja (ingresos y gastos) para la intención "¿cómo va la caja?"? (DATA_MODEL, `cash_movement`)
4. ¿La colaboradora puede ver costos y generar cotizaciones? (API.md, roles)
5. Reglas de redondeo y margen por defecto de las cotizaciones: validarlas con una emprendedora real (T05).
6. ¿Se puede conseguir una o dos emprendedoras de catering para fotos reales, recetas y una cotización manual de referencia? Sin eso, F2 y la métrica de tiempo de cotización quedan con datos sintéticos.
7. Licencia del proyecto (README: "por definir").
