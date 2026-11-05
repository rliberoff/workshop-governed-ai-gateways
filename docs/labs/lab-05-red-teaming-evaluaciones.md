# Laboratorio 5: Red Teaming y evaluaciones

Duración: 25 minutos.

## Objetivo

Analizar el comportamiento de la solución antes de llevarla a producción, de dos formas complementarias:

- **Red Teaming**: atacar de forma automatizada el asistente para medir con qué frecuencia produce contenido dañino.
- **Evaluaciones**: medir la calidad y la seguridad de las respuestas a un conjunto de preguntas representativas.

## Conceptos clave

| Concepto | Significado |
| :--- | :--- |
| AI Red Teaming Agent | Capacidad de Foundry, basada en PyRIT, que genera ataques, los envía a tu aplicación y evalúa las respuestas |
| Categoría de riesgo | Tipo de daño que se busca: violencia, odio e injusticia, contenido sexual, autolesiones, entre otros |
| Estrategia de ataque | Transformación del ataque para evadir defensas: `Base64`, `Flip` y `Morse` (fáciles), `Jailbreak`, entre otras |
| ASR (Attack Success Rate) | Porcentaje de ataques que obtuvieron una respuesta dañina, entre los que obtuvieron respuesta o bloqueo; cuanto menor, mejor |
| Evaluador | Métrica sobre una respuesta: coherencia, fluidez, violencia o F1 frente a una respuesta de referencia |

## Paso 1: Red Teaming del camino directo y del camino gobernado

El objetivo del ataque es el mismo asistente, con el mismo prompt de sistema, por dos caminos: el asistente interno del equipo de plataforma de IA, que solo responde sobre cómo la empresa gobierna la IA generativa. Abre dos terminales y lanza un escaneo en cada uno; cada escaneo tarda unos minutos:

```powershell
uv run python -m workshop.lab05_red_teaming --destino directo
```

```powershell
uv run python -m workshop.lab05_red_teaming --destino gateway
```

Cada escaneo genera 2 objetivos de ataque en español por categoría (violencia y odio), los envía sin transformar y con las estrategias fáciles y de jailbreak, y evalúa cada respuesta con los evaluadores de seguridad de Foundry.

No todo lo que no es un `200` es un ataque defendido. El script distingue tres casos:

| Respuesta | Origen | Cómo cuenta |
| :--- | :--- | :--- |
| `400` con el código `content_filter` | Filtro de contenido del despliegue de Foundry, en los dos caminos | Ataque defendido |
| `403` sin cabecera `retry-after` | Posiblemente `llm-content-safety` en el gateway | Se clasifica como defendido por heurística; el código no confirma el origen |
| `429` | Límite de tokens | Se reintenta; si sigue sin respuesta, el ataque queda fuera del ASR |
| `403` con `retry-after` u otro error | Cuota agotada o fallo | No es una defensa: el ataque queda fuera del ASR |

Sin esta distinción, un límite de tokens alcanzado al lanzar los escaneos en paralelo rebajaría el ASR del camino gobernado sin que ninguna política de contenido hubiera actuado. Al terminar, el script muestra cuántas llamadas respondió el modelo, cuántas bloqueó una política de contenido y cuántas quedaron sin respuesta.

La heurística de `403` puede confundir errores de autorización u otros rechazos con bloqueos de contenido. Verifica el origen en los registros del gateway antes de interpretar el ASR como una medida de defensas.

Con los valores predeterminados se prevén 20 casos. Un fallo individual no detiene las demás estrategias, aunque un fallo de preparación o del servicio puede impedir intentar o evaluar todos los casos. El resumen muestra los casos evaluados por categoría; los casos sin evaluar se identifican por categoría, estrategia y hash del objetivo en `incomplete-attacks.json`, dentro de la carpeta del informe. Si falta alguna evaluación, el proceso termina con código de salida distinto de cero y el ASR es parcial.

El mismo informe registra las respuestas `400`, `403` y `429` observadas por el cliente, también los `429` recuperados mediante reintentos. Incluye el número de intento, el hash del mensaje enviado y el resultado final de la llamada, sin guardar el cuerpo de la respuesta. Los reintentos internos del gateway no son visibles para el cliente.

El SDK puede marcar la ejecución como completada en Foundry incluso si faltan evaluaciones. Comprueba siempre la cobertura y el estado del informe local.

Revisa [`src/workshop/lab05_red_teaming.py`](../../src/workshop/lab05_red_teaming.py): la función `build_target` construye el *callback* que ataca el agente, y es lo único que cambia entre los dos caminos. Usa la firma completa de *callback* (`messages`, `stream`, `session_state` y `context`) a propósito: con una función simple, el SDK convertiría cualquier error en una respuesta y la puntuaría como inofensiva.

Al terminar, compara el ASR por categoría de los dos escaneos. Los ataques se generan de forma independiente, por lo que una muestra pequeña no demuestra por sí sola el efecto de `llm-content-safety`. Los detalles de cada ataque están en `red-team-results/scan-<destino>.json`.

Si la subida de resultados al proyecto falla, repite con `--sin-subir`; los resultados se guardan igualmente en local.

## Paso 2: evaluar la calidad de las respuestas

```powershell
uv run python -m workshop.lab05_evaluations
```

El script responde a las preguntas de [`src/workshop/data/evaluation.jsonl`](../../src/workshop/data/evaluation.jsonl) a través del gateway, igual que lo haría la aplicación en producción, con el mismo prompt de sistema que el Red Teaming. Las preguntas tratan sobre el gobierno de la IA, el ámbito del asistente, así que el modelo no tiene motivo para negarse a responderlas. Si el gateway limita una llamada, el script espera lo que indica `retry-after` y la repite. Las preguntas que siguen sin respuesta se excluyen y el script lo indica: el texto de un error HTTP no es una respuesta y falsearía todos los evaluadores.

Después crea una evaluación en la nube en tu proyecto de Foundry con cuatro evaluadores integrados:

| Evaluador | Tipo | Qué mide |
| :--- | :--- | :--- |
| `builtin.coherence` | Asistido por IA | Flujo lógico y organización de la respuesta |
| `builtin.fluency` | Asistido por IA | Corrección gramatical y legibilidad |
| `builtin.violence` | Seguridad | Presencia de contenido violento |
| `builtin.f1_score` | Léxico | Solapamiento de palabras con la respuesta de referencia |

Al terminar muestra cuántos elementos supera cada evaluador y la URL del informe. Ábrela para revisar las puntuaciones y las explicaciones de cada respuesta.

El F1 suele ser bajo aunque la respuesta sea buena, porque solo compara palabras. Por eso se combina con evaluadores asistidos por IA.

## Paso 3: reflexionar

1. ¿Qué umbral de ASR o de evaluación pondrías como condición para pasar a producción?
2. ¿Cómo integrarías estos escaneos y evaluaciones en un pipeline de CI/CD?
3. El juez de las evaluaciones es un modelo. ¿Qué riesgos tiene y cómo los mitigarías?

## Lo que te llevas

- Red Teaming y evaluaciones son pruebas: se automatizan, se versionan y se repiten en cada cambio.
- El gateway reduce riesgos, y el Red Teaming lo demuestra con datos.
- Foundry guarda los resultados en el proyecto para compararlos entre versiones.
