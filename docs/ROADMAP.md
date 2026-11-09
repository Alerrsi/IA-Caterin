# Roadmap — Cáterin

- Estado: 9-nov-2026. Este documento guarda las ideas que **no entran al MVP**, para no perderlas y para dejar claro que no se implementan sin pedido explícito (`AGENTS.md`, sección 2).

## 1. Ideas del brainstorming fuera de alcance

Ideas que surgieron en el brainstorming del informe "Detección de Oportunidades PYME – Cáterin" y que no se eligieron para el MVP.

| Idea | Por qué no entra ahora | Qué haría falta para retomarla |
|------|------------------------|--------------------------------|
| Robot de delivery | Costo de hardware, regulación y mantención muy lejos del presupuesto de una pyme | Validar la demanda; está fuera del foco de software |
| Detección de ataques informáticos con ML | No es un problema de la usuaria objetivo; existen soluciones genéricas | Buenas prácticas de seguridad estándar (SECURITY.md) cubren el MVP |
| Marketing con IA (publicaciones, campañas) | No apunta a la pregunta de desafío (finanzas, inventario, comunicación operativa); mercado saturado de herramientas | Podría reutilizar el LLM para redactar publicaciones con datos de la pyme |
| App de voz | Reconocimiento de voz en español de Chile con ruido de cocina es costoso en CPU; agrega latencia | Medir Whisper pequeño en CPU; empezar con dictado del teclado del teléfono |
| Pagos en línea | Requiere integración con pasarelas, comisiones y cumplimiento | Integrar una pasarela chilena si las usuarias lo piden |
| Facturación electrónica SII | Requiere certificación y un proveedor autorizado; alto riesgo legal | Integrar con un proveedor de facturación existente vía API |
| Expansión de infraestructura de telecomunicaciones | Fuera del alcance de un producto de software | — (el MVP mitiga con offline, ADR-004) |

## 2. Trabajo futuro relacionado con el MVP

### Asistente (F1)
- **Nivel 3 (agente con herramientas de solo lectura)** con `qwen3:8b`, `qwen3:14b` o un proveedor externo, solo si hay GPU o consentimiento para enviar datos minimizados (ADR-005).
- Reranker encendido si T10 demuestra beneficio.
- Intenciones nuevas a partir de las preguntas que caen en "no sé" (`assistant_interaction`).
- Respuestas proactivas: "mañana tienes un pedido y te falta harina" (notificación, sin LLM).

### Visión (F2)
- Clasificador de recortes como segunda etapa si hay confusión entre productos parecidos.
- Inferencia en el teléfono (ONNX Runtime Web) para contar sin red.
- Reentrenamiento periódico con las correcciones de las usuarias (aprendizaje activo).
- Estimar el peso o la porción, no solo contar.

### Cotización (F3)
- Fuentes de precios automáticas (`PriceSource`) con scraping **solo** de sitios cuyos términos lo permitan, aprobado en un ADR.
- Sub-recetas (masas, salsas base).
- Plantillas de PDF con la marca de la pyme.
- Envío de la cotización por WhatsApp o correo (requiere decidir el proveedor y los datos personales).
- Historial de precios y alertas de alza.

### Plataforma
- Una usuaria en varias pymes (tabla de membresías).
- Escalar a varias instancias de la API (caché compartida, ADR nuevo).
- Exportar a Excel para quien quiera seguir usando sus planillas.
- Modo de demostración con datos sintéticos que se reinicia solo.
