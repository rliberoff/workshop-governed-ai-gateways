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
| ASR (Attack Success Rate) | Porcentaje de ataques que obtuvieron una respuesta dañina; cuanto menor, mejor |
| Evaluador | Métrica sobre una respuesta: coherencia, fluidez, violencia o F1 frente a una respuesta de referencia |

## Paso 1: Red Teaming del camino directo y del camino gobernado

El objetivo del ataque es el mismo asistente, con el mismo prompt de sistema, por dos caminos. Abre dos terminales y lanza un escaneo en cada uno; cada escaneo tarda unos minutos:

```powershell
uv run python -m workshop.lab05_red_teaming --destino directo
```

```powershell
uv run python -m workshop.lab05_red_teaming --destino gateway
```

Cada escaneo genera 2 objetivos de ataque en español por categoría (violencia y odio), los envía sin transformar y con las estrategias fáciles y de jailbreak, y evalúa cada respuesta con los evaluadores de seguridad de Foundry. Cuando el gateway bloquea una petición, el script devuelve un texto de bloqueo que cuenta como ataque defendido.

Revisa [`src/workshop/lab05_red_teaming.py`](../../src/workshop/lab05_red_teaming.py): la función `build_target` construye el *callback* que ataca el agente, y es lo único que cambia entre los dos caminos.

Al terminar, compara el ASR por categoría de los dos escaneos. Con `llm-content-safety` activo, el camino gobernado debería mostrar un ASR igual o menor. Los detalles de cada ataque están en `red-team-results/scan-<destino>.json`.

Si la subida de resultados al proyecto falla, repite con `--sin-subir`; los resultados se guardan igualmente en local.

## Paso 2: evaluar la calidad de las respuestas

```powershell
uv run python -m workshop.lab05_evaluations
```

El script responde a las preguntas de [`src/workshop/data/evaluation.jsonl`](../../src/workshop/data/evaluation.jsonl) a través del gateway, igual que lo haría la aplicación en producción. Después crea una evaluación en la nube en tu proyecto de Foundry con cuatro evaluadores integrados:

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
