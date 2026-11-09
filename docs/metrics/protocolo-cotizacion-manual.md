# Protocolo de medición manual (línea base de T09)

- Estado: listo para usar (9-nov-2026). Todavía **no hay mediciones reales registradas**: sin ellas, el panel no compara el antes y el después y lo advierte.
- Relación: `docs/tasks/T09-metricas.md`, `AGENTS.md` (sección 10, honestidad con los datos).

El objetivo es **medir** cuánto tarda hoy la emprendedora sin Cáterin, para comparar con lo que mide la app. El tiempo "antes" no se toma de Winnow, MarketMan, del informe ni de una estimación: se cronometra con este protocolo.

Se miden dos cosas:

1. **Cotizar un pedido a mano** (comparación con el tiempo de cotización de Cáterin).
2. **Buscar un dato a mano** (comparación con el tiempo de respuesta del asistente).

## 1. Reglas comunes

- **Quién mide:** una persona del equipo con un cronómetro (el del celular sirve). La emprendedora hace la tarea como la hace siempre; quien mide no ayuda ni apura.
- **Quién hace la tarea:** la misma persona que después usará Cáterin. Si no se puede, una persona comparable (misma experiencia con el negocio y con planillas) y se anota en `notes`.
- **Herramientas:** las de siempre (Excel, cuaderno, calculadora, WhatsApp, listas de precios impresas). Se anota en `tool`.
- **Repeticiones:** al menos **3 por caso** y, si se puede, **5 o más** en total por tipo de tarea. El panel advierte cuando hay menos de 5 mediciones.
- **Orden:** para no favorecer a Cáterin por aprendizaje, alternar cuando se pueda: un caso a mano y luego con la app, y en la repetición siguiente al revés. Anotarlo en `notes`.
- **Datos personales:** el campo `reference` describe el caso ("pedido de referencia P1", "stock de harina"), **nunca** el nombre, teléfono ni dirección de un cliente.
- **Interrupciones:** si hay una interrupción de más de 1 minuto (llamada, cliente en el local), se pausa el cronómetro; si no se pudo pausar, se descarta la medición y se repite.
- **Datos sintéticos:** si la medición se hace con la pyme de demo o con un pedido inventado, se anota "sintético" en `notes` y así se informa.

## 2. Cotización manual

### Pedido de referencia

Se usan **los mismos pedidos** a mano y en Cáterin. Se recomiendan dos:

| Caso | Contenido (ejemplo a validar con la emprendedora) |
|------|----------------------------------------------------|
| P1 (simple) | 2 productos de recetas conocidas, sin ambigüedades, cantidades en unidades |
| P2 (típico) | 4 a 6 productos, alguno en docenas, uno con nombre ambiguo ("empanadas") y fecha relativa ("el sábado") |

Los pedidos se escriben como llegan de verdad (texto de WhatsApp). Si hay pedidos reales, se usan anonimizados.

### Qué se cronometra

- **Inicio:** cuando la persona recibe el texto del pedido (se lo entregan impreso o en el celular).
- **Fin:** cuando tiene el **total del pedido para el cliente** (con margen e IVA, como lo cotiza normalmente). No incluye redactar el mensaje de respuesta ni enviarlo.
- En Cáterin, la app mide lo equivalente: desde que se abre la pantalla **Cotizar un pedido** hasta que llega la cotización calculada (`POST /metrics/quote-timing`). Leer el PDF o enviarlo tampoco cuenta.

### Cómo se registra

En la PWA: **Mis métricas → Registrar una medición a mano**, con "Una cotización a mano". O por la API:

```http
POST /api/v1/metrics/manual-baseline
{
  "task": "quote",
  "seconds": 1470,
  "reference": "pedido de referencia P2",
  "repetition": 1,
  "measured_on": "2026-11-12",
  "tool": "Excel",
  "notes": "misma persona; primero a mano"
}
```

Además, quien mide anota en una hoja aparte el total al que llegó a mano y el de Cáterin. Si difieren, se revisa por qué (precio desactualizado, merma, redondeo) antes de comparar tiempos: una cotización rápida pero mal calculada no es una mejora.

## 3. Buscar un dato a mano

Compara el tiempo del asistente (F1) con lo que tarda la emprendedora en encontrar el mismo dato sin él.

### Preguntas de referencia

Elegir 3 a 5 preguntas que la emprendedora se hace de verdad, una por intención frecuente, por ejemplo:

| Caso | Pregunta | Dónde lo busca hoy (ejemplo) |
|------|----------|------------------------------|
| L1 | ¿Cuánta harina me queda? | Planilla de inventario |
| L2 | ¿Cuánto me cuesta hacer una docena de empanadas de pino? | Planilla de costos o cuaderno |
| L3 | ¿Qué pedidos tengo esta semana? | Cuaderno, calendario o WhatsApp |
| L4 | ¿Quién me vende más barato el aceite? | Listas de precios de proveedores |

### Qué se cronometra

- **Inicio:** cuando quien mide lee la pregunta en voz alta.
- **Fin:** cuando la persona dice el dato (aunque sea aproximado; se anota si fue correcto).
- Si no encuentra el dato en 5 minutos, se detiene, se registra 300 s y se anota "no lo encontró" en `notes`.
- En Cáterin, el asistente guarda su latencia en `assistant_interaction.latency_ms` (desde que llega la pregunta hasta la respuesta completa). La comparación justa es con la misma pregunta, **escrita** o con el botón rápido; se anota cuál.

### Cómo se registra

Igual que la cotización, con "Buscar un dato a mano" (`"task": "data_lookup"`) y `reference` = el caso ("L1 stock de harina").

## 4. Cómo se lee el resultado

- El panel muestra la **mediana** de cada lado con su **n**. Con n < 5 aparece "Pocas mediciones": se informa como **estudio piloto**, no como resultado.
- Las mediciones manuales **no se recortan por el periodo** del panel: son la línea base del "antes" y se muestran con las fechas en que se midieron. El tiempo con Cáterin sí se filtra por el periodo elegido.
- La exportación CSV (`GET /metrics/summary.csv`, o el botón **Descargar CSV**) lleva cada cifra con su n, si el n es bajo y su periodo, para pegarla en el informe.
- Si Cáterin no resulta más rápido, se informa tal cual y se proponen mejoras; **no** se cambia el protocolo ni el criterio para que el número salga mejor (`AGENTS.md`, sección 10).

## 5. Vista agregada para el equipo

Para el informe con varias pymes (sin pasar por la API ni por una cuenta de dueña), en el servidor:

```bash
docker compose -f infra/docker-compose.yml exec api python -m app.modules.metrics.report --exclude-demo
docker compose -f infra/docker-compose.yml exec api python -m app.modules.metrics.report --exclude-demo --csv > metricas-equipo.csv
```

`--exclude-demo` deja fuera la pyme de demo (datos sintéticos). Acepta `--from` y `--to` (AAAA-MM-DD).
