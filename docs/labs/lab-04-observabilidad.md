# Laboratorio 4: trazabilidad y observabilidad

Duración: 20 minutos.

## Objetivo

Reconstruir qué ha pasado en cada interacción con el modelo: quién llamó, cuántos tokens consumió y con qué resultado, y cómo se encadenan la aplicación, el gateway y el modelo en una misma traza.

## Qué se registra y dónde

| Señal | Origen | Destino | Configuración |
| :--- | :--- | :--- | :--- |
| Métricas de tokens por suscripción, producto y API | Política `llm-emit-token-metric` | Métricas personalizadas de Application Insights | [`policies/api.xml.tftpl`](../../inf/resources/modules/apim/policies/api.xml.tftpl) |
| Peticiones del gateway | API Management | Tabla `ApiManagementGatewayLogs` | `azurerm_api_management_api_diagnostic.azure_monitor` |
| Peticiones con contexto W3C | API Management | Application Insights | `azapi_resource.api_diagnostic_appi` |
| Spans GenAI de la aplicación | Scripts del taller | Application Insights | [`src/workshop/telemetry.py`](../../src/workshop/telemetry.py) |
| Vista de trazas del proyecto | Microsoft Foundry | Application Insights conectado | `azapi_resource.project_connection_appi` |

La política integrada `llm-emit-token-metric` publica las métricas `Prompt Tokens`, `Completion Tokens` y `Total Tokens` en el espacio de nombres `governed-ai-gateways`, con las dimensiones `Subscription ID`, `Product ID` y `API ID`. Necesita dos ajustes que Terraform aplica por ti: las métricas personalizadas con dimensiones en Application Insights (`azapi_update_resource.custom_metrics_with_dimensions`) y `metrics: true` en el diagnóstico de Application Insights de la API.

Application Insights se basa en el mismo workspace de Log Analytics y tiene la autenticación local desactivada: tanto el gateway como tú enviáis telemetría con Microsoft Entra ID.

## Paso 1: generar una conversación trazada

```powershell
uv run python -m workshop.lab04_observability generar
```

El script configura OpenTelemetry con el exportador de Azure Monitor, abre un span padre `lab04.conversation` y hace tres llamadas a través del gateway. Cada llamada crea un span cliente con atributos de las convenciones semánticas GenAI, como `gen_ai.request.model`, `gen_ai.usage.input_tokens` y `gen_ai.usage.output_tokens`, y envía la cabecera `traceparent` al gateway. Al final imprime el *trace ID*; guárdalo.

Revisa la función `chat` en [`src/workshop/chat.py`](../../src/workshop/chat.py) para ver cómo se crean los spans y se propaga el contexto con `inject`.

## Paso 2: consultar las métricas y los registros del gateway

La ingesta tarda entre 2 y 5 minutos. Mientras tanto, abre las consultas KQL en [`src/workshop/queries/`](../../src/workshop/queries/). Después ejecútalas:

```powershell
uv run python -m workshop.lab04_observability consultas
```

| Consulta | Qué responde |
| :--- | :--- |
| `tokens` | Tokens de entrada, salida y total por suscripción y producto, a partir de las métricas de `llm-emit-token-metric`: el consumo de `app-basico` frente a `app-premium` |
| `estados` | Respuestas por suscripción y código: los `401`, `429` y `403` del laboratorio 2 |

También puedes pegarlas en **Logs** del workspace de Log Analytics. Para ver las mismas métricas como gráfico, abre Application Insights en el portal, ve a **Metrics**, elige el espacio de nombres `governed-ai-gateways` y la métrica `Total Tokens` con agregación **Sum**, y divide por `Subscription ID`. Solo es una consulta: no cambia ninguna configuración.

## Paso 3: seguir una traza de extremo a extremo

```powershell
uv run python -m workshop.lab04_observability traza --id <trace-id>
```

Verás en orden los spans que comparten el mismo `OperationId`: la conversación y las llamadas del script (`AppDependencies`, rol `workshop-lab04`) y las peticiones recibidas por el gateway (`AppRequests`, rol de API Management). Puedes explorar la misma traza en Application Insights, en **Búsqueda de transacciones**, y en la vista de trazas del proyecto de Foundry.

## Paso 4: reflexionar

1. ¿Qué ventaja tiene que los tokens se midan en el gateway y no en cada aplicación?
2. ¿Qué alerta pondrías sobre la métrica `Total Tokens` para detectar a tiempo que un producto se acerca a su cuota?
3. ¿Qué información aporta el span de la aplicación que el gateway no puede conocer?

## Para profundizar

- Azure Monitor limita las métricas personalizadas: como máximo 5 dimensiones por política, 100 valores únicos por dimensión y 1.000 series activas por espacio de nombres. Elige dimensiones de baja cardinalidad, como suscripción o producto, y evita la IP o el usuario final.
- Puedes reducir costes con muestreo en los diagnósticos de API Management.

## Lo que te llevas

- El gateway mide el consumo de forma uniforme con una política integrada y deja un registro auditable de cada petición.
- La propagación W3C une aplicación, gateway y modelo en una única traza.
- OpenTelemetry con las convenciones GenAI es el idioma común de Foundry, Azure Monitor y Unity Gateway.
