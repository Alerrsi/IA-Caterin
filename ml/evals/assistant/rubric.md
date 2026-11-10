# Rúbrica de revisión humana de la redacción del asistente (T10)

Se aplica a las respuestas de **nivel 1** (el LLM redacta un dato ya resuelto) y **nivel 2** (el LLM resume fragmentos de documentos). La planilla sale de `make_review_sheet.py`. Cada respuesta la revisan **al menos 2 personas del equipo, por separado**, sin ver la nota de la otra.

Cada criterio se califica de 1 a 3. Si dudas entre dos notas, pon la más baja y explica por qué en el comentario.

## 1. Corrección (¿dice la verdad según el dato?)

| Nota | Criterio | Ejemplo (dato: "Producir 12 unidades de Empanadas de queso te cuesta $9.156 ($763 por unidad)") |
|------|----------|------|
| 3 | Todo lo que afirma está en el dato de entrada. No omite nada que cambie la decisión (p. ej. "el total es parcial"). | "La docena de empanadas de queso te cuesta $9.156, unos $763 cada una." |
| 2 | Es correcta, pero omite un matiz importante o redondea de una forma que puede confundir. | "Te sale como $9 mil la docena." (redondea y no dice que incluye IVA) |
| 1 | Afirma algo que no está en el dato, lo contradice o confunde unidades o productos. | "La docena cuesta $763." (confunde el total con el precio por unidad) |

En el nivel 2, "el dato" son los fragmentos citados. Si la respuesta no está en ellos, lo correcto es decir que no aparece en sus documentos.

## 2. Claridad (¿se entiende a la primera, desde el celular?)

| Nota | Criterio | Ejemplo |
|------|----------|---------|
| 3 | 1 a 3 frases cortas, con la cifra o la respuesta al principio. No hace falta releer. | "Sí, el refrigerador debe estar entre 1 y 4 °C. Se anota dos veces al día." |
| 2 | Se entiende, pero da rodeos, repite o pone la respuesta al final. | "Según el protocolo de higiene que tienes cargado, hay varias indicaciones, y una de ellas es que…" |
| 1 | Confusa, larga, con listas innecesarias o en otro idioma. | "Okay, let's see. The user is asking…" |

## 3. Tono chileno natural (¿suena como le hablaría una persona de confianza?)

| Nota | Criterio | Ejemplo |
|------|----------|---------|
| 3 | Español de Chile neutro y cercano. Tutea, sin modismos forzados y sin sonar a traducción. | "Te quedan 18 kg de harina; te alcanza para esta semana." |
| 2 | Correcto, pero rígido o con algún giro de otro país ("usted", "ordenar" por "pedir", "ahorita"). | "Usted dispone de 18 kilogramos de harina." |
| 1 | Suena a traducción, a otro país o a máquina, o usa chilenismos exagerados. | "Weón, te quedan 18 lucas de harina po." |

## Reglas para revisar

- Revisa con el **dato de entrada** a la vista (columna `dato_de_entrada`). No uses lo que sabes del negocio.
- Si el sistema descartó la respuesta del LLM (`motivo_descartada` no está vacío), califica igual la respuesta del LLM: sirve para saber qué tan seguido se equivoca. La usuaria vio `respuesta_mostrada`.
- Al final, se calcula el promedio por criterio y nivel, y el **acuerdo entre revisores** (porcentaje de respuestas con la misma nota).
- **Umbral propuesto para encender `ASSISTANT_USE_LLM` por defecto:** corrección promedio ≥ 2,8 sin ninguna nota 1 en corrección, y claridad y tono ≥ 2,5. El equipo debe ratificarlo; si no se alcanza, el asistente sigue respondiendo con plantillas (nivel 0) y fragmentos citados (nivel 2 extractivo).
