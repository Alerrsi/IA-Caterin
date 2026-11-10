# T12 — Documentación final y demo
- Estado: pendiente
- Depende de: T09, T10, T11
- Funcionalidad: transversal

## Objetivo
Que cualquiera pueda instalar Cáterin siguiendo el README, que una emprendedora aprenda a usarlo sola con una guía simple, y que la presentación final muestre en 10 minutos el valor real con datos medidos.

## Contexto y decisiones previas
- Criterios globales del MVP: `AGENTS.md`, sección 9.
- Honestidad con los datos: `AGENTS.md`, sección 10. Los datos de demo se marcan como sintéticos.

## Entregables
- [ ] `README.md` final: puesta en marcha verificada desde cero en una máquina limpia, enlaces a la documentación, licencia elegida.
- [ ] `docs/GUIA_USUARIA.md`: lenguaje simple, con capturas, para las 5 acciones principales; qué funciona sin señal; qué hacer si algo falla.
- [ ] `docs/DEMO.md`: guion de 10 minutos (problema → cargar insumos y receta → cotizar desde un mensaje de WhatsApp → contar con foto → preguntar al asistente → métricas medidas), con tiempos por bloque y plan B si falla la red o el LLM.
- [ ] Seed de demo (`python -m app.db.seed --demo`) con una pyme ficticia coherente con el guion, marcada como sintética.
  - Avance (10-nov-2026): `python -m app.db.demo_full` crea "Banquetería Volcán Llaima (demo)", que llena todas las tablas con volumen (ver README). Usa los servicios reales: cotizaciones, portal, documentos y asistente sin LLM. Las métricas que crea son inventadas y llevan `"synthetic": true`; la pyme es `is_demo`, así que el panel global puede excluirlas. Prueba: `tests/test_demo_full.py`. Falta ajustarla al guion de la demo.
- [ ] Revisión final de que la documentación coincide con el código (ADR, API, DATA_MODEL).
- [ ] Resumen de cierre en cada tarea y estados al día en `00-INDEX.md`.

## Criterios de aceptación
- Una persona del equipo que no hizo T01 instala desde cero siguiendo solo el README, sin ayuda, y anota los problemas que encontró (se corrigen).
- La demo se ensaya al menos dos veces y dura ≤ 10 minutos.
- Toda cifra mostrada en la demo viene del informe de T10 o del panel de T09, con su n y su fecha.

## Pruebas requeridas
- Ejecución real de todos los comandos del README y de la guía.

## Fuera de alcance
- Video promocional, sitio web de marketing.

## Riesgos y preguntas abiertas
- La red de la sala de presentación: tener la demo funcionando en local como respaldo.

## Resumen de cierre
(se completa al terminar)
