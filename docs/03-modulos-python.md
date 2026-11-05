# Módulos Python del taller

Esta guía explica el código de [src/workshop](../src/workshop), cómo se relacionan sus módulos y qué ejecuta cada laboratorio. Complementa la [preparación del entorno](00-preparacion.md) y las guías de [laboratorios](labs/).

## Cómo ejecutar los módulos

Ejecuta los comandos desde la raíz del repositorio, con las dependencias instaladas y el entorno de `azd` seleccionado. La configuración de empaquetado de [pyproject.toml](../pyproject.toml) incluye `src/workshop`, de modo que Python puede encontrar el paquete por su nombre.

Para realizar una llamada directa al modelo, ejecuta:

```powershell
uv run python -m workshop.lab01_direct --repeticiones 1
```

`uv run` ejecuta Python en el entorno del proyecto. `-m` ejecuta el módulo `workshop.lab01_direct`, correspondiente al archivo del laboratorio 1. El argumento `--repeticiones 1` limita la ejecución a una llamada.

Los módulos de laboratorio tienen una función `main()` que procesa los argumentos y un bloque `if __name__ == "__main__"` que la invoca. Los módulos compartidos ofrecen funciones y clases para esos laboratorios; no son comandos independientes.

Las llamadas al modelo son reales y consumen tokens. Las evaluaciones y el red teaming también usan servicios remotos y pueden generar costes. Estos scripts no sustituyen el despliegue de infraestructura con Terraform.

## Configuración y componentes compartidos

### workshop

El archivo [src/workshop/__init__.py](../src/workshop/__init__.py) identifica el paquete principal. Solo contiene una descripción: no inicia laboratorios, carga configuración ni realiza llamadas remotas al importarlo.

### workshop.config

Código: [src/workshop/config.py](../src/workshop/config.py).

Centraliza la configuración en dos clases de datos inmutables:

- `Settings`: entorno, suscripción, grupo de recursos, cuentas y proyectos de Foundry, endpoint directo, modelo, APIM, Log Analytics y esfuerzo de razonamiento
- `DatabricksSettings`: URL e identificador del workspace, model provider service y esquema de Databricks

`load_settings()` ejecuta `azd env get-values --output json`, valida los valores obligatorios y devuelve un objeto `Settings`. Conserva el resultado en caché durante el proceso. No requiere escribir un archivo de configuración adicional para Python.

El endpoint directo procede de `FOUNDRY_OPENAI_V1_ENDPOINT` y el nombre del despliegue de `FOUNDRY_MODEL_DEPLOYMENT_NAME`. `MODEL_REASONING_EFFORT` usa `low` por defecto; un valor vacío desactiva el envío de ese parámetro.

Los datos de Databricks son opcionales: si falta alguno de sus cuatro valores, `settings.databricks` es `None`. Los demás valores obligatorios se validan incluso cuando el laboratorio concreto no los utiliza. Si no existen, el módulo indica que debe completarse la capa `resources`.

### workshop.clients

Código: [src/workshop/clients.py](../src/workshop/clients.py).

Construye clientes compatibles con OpenAI para tres rutas:

| Función | Destino | Autenticación |
| :--- | :--- | :--- |
| `direct_client()` | Endpoint OpenAI v1 de Foundry | Token de Microsoft Entra ID del participante |
| `apim_client()` | API gobernada de API Management | Clave de suscripción del producto |
| `unity_gateway_client()` | Ruta de Unity Gateway del workspace | Token de Databricks y cabecera del model provider service |

`credential()` comparte una instancia de `DefaultAzureCredential`, normalmente respaldada por la sesión de Azure CLI. `apim_subscription_key()` consulta la clave primaria mediante la API de administración de APIM; no la escribe en archivos ni la obtiene de una salida de Terraform.

El cliente de Unity Gateway carga el SDK de Databricks solo cuando se necesita y usa autenticación `azure-cli`. Requiere los valores de la capa opcional `databricks`.

Todos los clientes desactivan los reintentos automáticos del SDK con `max_retries=0`, para que los laboratorios puedan observar cada rechazo o limitación. Los reintentos deliberados se implementan en `chat_with_retry()`.

### workshop.chat

Código: [src/workshop/chat.py](../src/workshop/chat.py).

Concentra el envío de mensajes y la interpretación de las respuestas:

- `ChatResult` reúne código HTTP, texto, latencia, tokens de entrada y salida, cabeceras de gobierno e identificador de traza; `ok` indica si el estado está entre 200 y 299
- `chat()` envía una petición de chat completions, con mensaje de sistema opcional y un máximo predeterminado de 800 tokens de finalización
- `chat_with_retry()` repite las llamadas que devuelven `429`, con hasta cinco intentos por defecto; respeta `retry-after` o utiliza espera exponencial, con un máximo de 60 segundos por espera
- `describe()` prepara la salida de consola y acorta el texto a 300 caracteres por defecto

`chat()` crea un span de OpenTelemetry con atributos de modelo, operación, servidor, estado HTTP y uso de tokens. Propaga el contexto de traza mediante cabeceras W3C. La exportación de esos spans requiere configurar la telemetría.

Los errores HTTP se convierten en `ChatResult` con el estado recibido; los errores de conexión usan el código `0`. No se capturan aquí todas las excepciones posibles. Los resultados recogen, cuando existen, las cabeceras `x-tokens-consumed`, `x-ratelimit-remaining-tokens`, `x-quota-remaining-tokens` y `retry-after`.

`chat_with_retry()` no reintenta otros estados, como `403`: agotar una cuota no equivale a superar temporalmente el límite por minuto.

### workshop.foundry_gateway

Código: [src/workshop/foundry_gateway.py](../src/workshop/foundry_gateway.py).

Descubre los objetos de API Management que Foundry crea al habilitar su AI Gateway. No habilita el gateway ni modifica sus políticas.

`discover()` sigue los enlaces ARM del proyecto y consulta su producto, suscripción, API y operaciones. Devuelve un `GatewayArtifacts` con los datos necesarios para construir la llamada. Admite dos modos:

- `independiente`: usa la segunda cuenta y el segundo proyecto de Foundry
- `integrado`: usa la cuenta y el proyecto principales, asociados a la instancia APIM del taller

El descubrimiento busca una operación `POST` de chat completions y prefiere una ruta OpenAI v1 frente a una basada en despliegues. Calcula la URL base, la cabecera de clave y, cuando corresponde, el parámetro `api-version`.

`gateway_client()` obtiene la clave de la suscripción descubierta y devuelve el cliente OpenAI. `list_service_apis()` enumera las APIs de la instancia. Si el gateway o la asociación del proyecto todavía no existen, el módulo explica qué paso falta en el portal de Foundry.

### workshop.telemetry

Código: [src/workshop/telemetry.py](../src/workshop/telemetry.py).

Configura la exportación de trazas a Application Insights:

- `configure_tracing()` obtiene la cadena de conexión desde el proyecto de Foundry y configura Azure Monitor con credenciales de Microsoft Entra ID y un nombre de servicio
- `flush_tracing()` solicita exportar los spans pendientes antes de terminar el proceso, si el proveedor de trazas permite hacerlo

La cadena de conexión no se guarda en un archivo. El módulo presupone la conexión de Application Insights creada por Terraform y el permiso `Monitoring Metrics Publisher` del participante. Lo utiliza el laboratorio 4 al generar una conversación trazada.

## Módulos de laboratorio

### workshop.lab01_direct

Código: [src/workshop/lab01_direct.py](../src/workshop/lab01_direct.py). Guía: [laboratorio 1](labs/lab-01-consumo-directo.md).

Carga la configuración, construye un cliente directo a Foundry y pregunta al modelo qué es un AI gateway y por qué importa en una empresa. Imprime endpoint, modelo, estado HTTP, latencia, respuesta y tokens consumidos.

Para realizar una llamada, ejecuta:

```powershell
uv run python -m workshop.lab01_direct --repeticiones 1
```

`--repeticiones` vale 3 por defecto. El propósito es establecer el punto de partida sin las políticas centralizadas de APIM, no eliminar los filtros o las cuotas propios del servicio de modelos.

### workshop.lab02_gateway

Código: [src/workshop/lab02_gateway.py](../src/workshop/lab02_gateway.py). Guía: [laboratorio 2](labs/lab-02-ai-gateway-apim.md).

Consume la API gobernada de APIM. Define los mensajes corto y largo que reutilizan otros laboratorios y ofrece cuatro subcomandos:

| Subcomando | Comportamiento | Valores predeterminados |
| :--- | :--- | :--- |
| `llamar` | Envía una petición con una suscripción válida | `--producto basico` |
| `sin-clave` | Envía deliberadamente una clave no válida para observar el rechazo | Sin parámetros |
| `rafaga` | Envía peticiones consecutivas y cuenta los resultados por estado HTTP | `--producto basico --peticiones 20` |
| `seguridad` | Envía mensajes de prueba para observar los filtros de contenido | `--producto premium` |

Para probar el producto básico, ejecuta:

```powershell
uv run python -m workshop.lab02_gateway llamar --producto basico
```

La ráfaga no utiliza `chat_with_retry()`, porque interesa ver cada `429`. En esta demostración, un `429` refleja el límite de tokens por minuto y un `403` puede indicar una cuota agotada o un bloqueo de contenido, según la petición y la política.

### workshop.lab03_foundry_gateway

Código: [src/workshop/lab03_foundry_gateway.py](../src/workshop/lab03_foundry_gateway.py). Guía: [laboratorio 3](labs/lab-03-ai-gateway-foundry.md).

Usa `foundry_gateway` para inspeccionar y consumir el AI Gateway habilitado desde Foundry. Todos sus subcomandos requieren `--modo independiente` o `--modo integrado`:

- `inspeccionar`: muestra proyecto, instancia APIM, producto, suscripción, API, operaciones, URL y cabecera de autenticación; distingue la API creada por Terraform de la creada por Foundry
- `llamar`: envía una petición por la ruta descubierta
- `rafaga`: envía peticiones consecutivas, con `--peticiones 20` por defecto, y resume sus estados HTTP

Para inspeccionar el modo integrado, ejecuta:

```powershell
uv run python -m workshop.lab03_foundry_gateway inspeccionar --modo integrado
```

El script no crea los objetos que faltan ni cambia los límites configurados en Foundry. El subcomando de inspección no envía mensajes al modelo, aunque sí consulta las APIs de administración de Azure.

### workshop.lab04_observability

Código: [src/workshop/lab04_observability.py](../src/workshop/lab04_observability.py). Guía: [laboratorio 4](labs/lab-04-observabilidad.md).

Relaciona las llamadas del cliente con los registros y trazas del gateway:

- `generar`: configura la telemetría, abre el span padre `lab04.conversation`, realiza tres llamadas por APIM y muestra el identificador de traza; usa `--producto premium` por defecto
- `consultas`: ejecuta las consultas `estados` y `tokens`, o las seleccionadas con `--consulta`
- `traza`: requiere `--id` con un identificador obtenido al generar una conversación y consulta sus spans

Para consultar los registros disponibles, ejecuta:

```powershell
uv run python -m workshop.lab04_observability consultas --consulta estados tokens
```

Las consultas usan `LogsQueryClient` sobre el workspace de Log Analytics y una ventana de una hora. Los resultados pueden tardar unos minutos en aparecer por la ingesta. Consultar registros no envía nuevas peticiones al modelo; `generar` sí lo hace.

### workshop.lab05_red_teaming

Código: [src/workshop/lab05_red_teaming.py](../src/workshop/lab05_red_teaming.py). Guía: [laboratorio 5](labs/lab-05-red-teaming-evaluaciones.md).

Ejecuta pruebas adversariales automatizadas contra un asistente interno sobre gobierno de IA. Define `APPLICATION_SCENARIO` y `SYSTEM_PROMPT`; este último también lo usan las evaluaciones de calidad para mantener el mismo alcance del asistente.

`build_target()` crea la función asíncrona que recibe los mensajes de ataque. Envía las llamadas bloqueantes a un hilo y cuenta tres resultados: respuestas del modelo, bloqueos de contenido y llamadas sin respuesta válida. Un error de conexión, una limitación o una cuota agotada no se presentan como una defensa exitosa.

`scan()` configura el AI Red Teaming Agent con las categorías `Violence` y `HateUnfairness`, idioma español y estrategias `EASY` y `Jailbreak`. Muestra el ASR, o porcentaje de ataques exitosos, y guarda el informe en la carpeta local `red-team-results`.

Para analizar la ruta gobernada sin subir el resultado al proyecto, ejecuta:

```powershell
uv run python -m workshop.lab05_red_teaming --destino gateway --producto premium --objetivos 2 --sin-subir
```

`--destino` admite `directo` o `gateway` y usa `gateway` por defecto. El producto predeterminado es `premium` y hay dos objetivos por categoría por defecto. Sin `--sin-subir`, el análisis permite subir sus resultados a Foundry. Esa opción no convierte la prueba en local: sigue utilizando los servicios remotos y consumiendo tokens.

### workshop.lab05_evaluations

Código: [src/workshop/lab05_evaluations.py](../src/workshop/lab05_evaluations.py). Guía: [laboratorio 5](labs/lab-05-red-teaming-evaluaciones.md).

Evalúa la calidad y seguridad de respuestas obtenidas a través de APIM:

1. `load_dataset()` lee las preguntas y respuestas de referencia del paquete de datos.
2. `generate_answers()` consulta el modelo por el gateway, con el mensaje de sistema del red teaming y reintentos ante `429`.
3. Excluye las preguntas que no recibieron una respuesta HTTP satisfactoria, para no puntuar un mensaje de error como si fuera una respuesta del asistente.
4. `testing_criteria()` define coherencia, fluidez, violencia y puntuación F1.
5. `evaluate()` crea una evaluación y una ejecución en Foundry, consulta su estado cada cinco segundos y muestra resultados y URL del informe.

Para evaluar las respuestas del producto premium, ejecuta:

```powershell
uv run python -m workshop.lab05_evaluations --producto premium
```

`--producto` vale `premium` por defecto. Las respuestas se generan por APIM, pero la ejecución de los evaluadores se solicita al proyecto de Foundry. Si no se obtiene ninguna respuesta válida, el módulo termina con un error en lugar de crear una evaluación vacía.

### workshop.lab06_unity_gateway

Código: [src/workshop/lab06_unity_gateway.py](../src/workshop/lab06_unity_gateway.py). Guía: [laboratorio 6](labs/lab-06-unity-gateway.md).

Prueba Unity Gateway y compara las rutas del taller:

- `llamar`: envía una petición mediante el model provider service de Databricks
- `rafaga`: envía peticiones consecutivas, con `--peticiones 20` por defecto, para observar el límite por usuario
- `comparar`: usa el mismo mensaje por la ruta directa, APIM, los dos modos del AI Gateway de Foundry y Unity Gateway cuando está disponible; el producto APIM predeterminado es `premium`

Para comparar las rutas configuradas, ejecuta:

```powershell
uv run python -m workshop.lab06_unity_gateway comparar --producto premium
```

`llamar` y `rafaga` requieren la capa opcional de Databricks y su extra de dependencias. `comparar` puede funcionar sin esa capa y omite Unity Gateway si no está configurado. También omite un modo de Foundry si su descubrimiento produce un `RuntimeError`, explicando el motivo; no ignora todos los tipos de error.

El modo independiente de Foundry utiliza el despliegue de la segunda cuenta. Las demás rutas utilizan el de la cuenta principal.

## Paquetes de datos y consultas

### workshop.data

El archivo [src/workshop/data/__init__.py](../src/workshop/data/__init__.py) identifica el paquete de datos. No ejecuta lógica. Permite que `importlib.resources` encuentre [src/workshop/data/evaluation.jsonl](../src/workshop/data/evaluation.jsonl) como recurso del paquete.

El archivo JSONL contiene ocho casos con los campos `query` y `ground_truth`: preguntas de gobierno de IA y sus respuestas de referencia. El laboratorio de evaluaciones añade la respuesta real del modelo antes de enviarlas a Foundry. El red teaming no usa este archivo como su conjunto de ataques.

### workshop.queries

El archivo [src/workshop/queries/__init__.py](../src/workshop/queries/__init__.py) identifica el paquete de consultas. Tampoco ejecuta lógica. El laboratorio 4 lee sus archivos con `importlib.resources`:

| Recurso | Qué consulta |
| :--- | :--- |
| [src/workshop/queries/tokens-by-subscription.kql](../src/workshop/queries/tokens-by-subscription.kql) | Tokens de entrada, salida y totales en `AppMetrics`, agrupados por suscripción y producto |
| [src/workshop/queries/responses-by-status.kql](../src/workshop/queries/responses-by-status.kql) | Peticiones en `ApiManagementGatewayLogs`, agrupadas por suscripción, estado HTTP y motivo del error |
| [src/workshop/queries/end-to-end-trace.kql](../src/workshop/queries/end-to-end-trace.kql) | Registros de `AppRequests` y `AppDependencies` que comparten un `OperationId` |

Las tres consultas filtran la última hora. Para la consulta de traza, el laboratorio sustituye el identificador recibido por consola antes de enviarla al workspace.

## Relación entre los módulos

El flujo común de los laboratorios es cargar `Settings`, construir un cliente, llamar a `chat()` y mostrar el resultado con `describe()`. Las evaluaciones y el red teaming usan `chat_with_retry()` para esperar cuando el servicio limita temporalmente las peticiones.

`clients` y `config` proporcionan la base compartida. `foundry_gateway` añade el descubrimiento de las rutas administradas por Foundry, y `telemetry` activa la exportación que necesita el laboratorio de observabilidad. Los paquetes `data` y `queries` distribuyen archivos de entrada junto con el código, sin depender de rutas relativas al directorio desde el que se ejecuta Python.
