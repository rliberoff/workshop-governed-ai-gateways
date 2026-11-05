# Laboratorio 4: trazabilidad y observabilidad

Duración: 20 minutos.

## Objetivo

Reconstruir qué ha pasado en cada interacción con el modelo: quién llamó, cuántos tokens consumió y con qué resultado, y cómo se encadenan la aplicación, el gateway y el modelo en una misma traza.

## Qué se registra y dónde

| Señal | Origen | Destino | Configuración |
| :--- | :--- | :--- | :--- |
| Métricas de tokens por suscripción, producto y API | Política `llm-emit-token-metric` | Métricas personalizadas de Application Insights | [`policies/api.xml.tftpl`](../../inf/resources/modules/apim/policies/api.xml.tftpl) |
| Peticiones del gateway | API Management | Tabla `ApiManagementGatewayLogs` | `azapi_resource.api_diagnostic_azure_monitor` |
| Peticiones con contexto W3C | API Management | Application Insights | `azapi_resource.api_diagnostic_appi` |
| Spans GenAI de la aplicación | Scripts del taller | Application Insights | [`src/workshop/telemetry.py`](../../src/workshop/telemetry.py) |
| Vista de trazas del proyecto | Microsoft Foundry | Application Insights conectado | `azapi_resource.project_connection_appi` |

La política integrada `llm-emit-token-metric` publica las métricas `Prompt Tokens`, `Completion Tokens` y `Total Tokens` en el espacio de nombres `governed-ai-gateways`, con las dimensiones `Subscription ID`, `Product ID` y `API ID`. Necesita dos ajustes que Terraform aplica por ti: las métricas personalizadas con dimensiones en Application Insights (`azapi_resource_action.custom_metrics_with_dimensions`) y `metrics: true` en el diagnóstico de Application Insights de la API.

Application Insights se basa en el mismo workspace de Log Analytics y tiene la autenticación local desactivada: tanto el gateway como tú enviáis telemetría con Microsoft Entra ID.

## Paso 1: generar una conversación trazada

```powershell
uv run python -m workshop.lab04_observability generar
```

El script configura OpenTelemetry con el exportador de Azure Monitor, abre un span padre `lab04.conversation` y hace tres llamadas a través del gateway. Cada llamada crea un span cliente con atributos de las convenciones semánticas GenAI, como `gen_ai.request.model`, `gen_ai.usage.input_tokens` y `gen_ai.usage.output_tokens`, y envía la cabecera `traceparent` al gateway. Al final imprime el *trace ID*; guárdalo.

Revisa la función `chat` en [`src/workshop/chat.py`](../../src/workshop/chat.py) para ver cómo se crean los spans y se propaga el contexto con `inject`.

## Paso 2: consultar las métricas y los registros del gateway

La ingesta podría tardar entre 2 y 5 minutos en aparecer. Espera ese tiempo. Mientras tanto, abre las consultas KQL en [`src/workshop/queries/`](../../src/workshop/queries/). Después ejecútalas:

```powershell
uv run python -m workshop.lab04_observability consultas
```

| Consulta | Qué responde |
| :--- | :--- |
| `tokens` | Tokens de entrada, salida y total por suscripción y producto, a partir de las métricas de `llm-emit-token-metric`: el consumo de `app-basico` frente a `app-premium` |
| `estados` | Respuestas por suscripción y código: los `401`, `429` y `403` del laboratorio 2 |

También puedes pegarlas en **Registros** del workspace de Log Analytics `log-gaig-<entorno>-<sufijo>`. En el paso 4 verás las mismas métricas como gráfico en Application Insights.

## Paso 3: seguir una traza de extremo a extremo

```powershell
uv run python -m workshop.lab04_observability traza --id <trace-id>
```

Verás en orden los spans que comparten el mismo `OperationId`: la conversación y las llamadas del script (`AppDependencies`, rol `workshop-lab04`) y las peticiones recibidas por el gateway (`AppRequests`, rol de API Management). En el paso 4 recorrerás la misma traza en Application Insights; también puedes verla en la vista de trazas del proyecto de Foundry.

## Paso 4: explorar Application Insights en el portal

Todo lo que has consultado con los scripts se puede explorar en el portal de Azure. En este paso solo consultas datos: no cambies ninguna configuración, porque la gestiona Terraform. Ten a mano el *trace ID* del paso 1.

### Abrir Application Insights

1. Abre el [portal de Azure](https://portal.azure.com) con la cuenta del taller.
2. Escribe `appi-gaig-<entorno>-<sufijo>` en la barra de búsqueda superior y abre el recurso de Application Insights. Está en el grupo de recursos `rg-gaig-<entorno>-<sufijo>`.
3. Cada vista tiene su propio selector de intervalo de tiempo. Usa **Última hora** salvo que el paso indique otro.

### Comprobar las métricas personalizadas con dimensiones

1. En el menú lateral, en **Configurar**, selecciona **Uso y costos estimados**.
2. Selecciona **Métricas personalizadas (versión preliminar)** y comprueba que está marcada la opción **Con dimensiones**.
3. Cierra el panel con la **X**, sin pulsar **Aceptar**: ese botón guarda la opción marcada en ese momento. Terraform aplica este ajuste con la propiedad `CustomMetricsOptedInType`; sin él, Azure Metric Store descartaría las dimensiones `Subscription ID`, `Product ID` y `API ID` de las métricas de tokens. Log Analytics las conserva siempre en la tabla `AppMetrics`.
4. Si aparece **Sin dimensiones**, no lo cambies en el portal y avisa al instructor. El ajuste no es retroactivo: las métricas recibidas mientras estaba desactivado no tienen dimensiones en Azure Metric Store, aunque la consulta KQL del paso 2 sí las muestre.

### Ver el consumo de tokens en Métricas

1. En **Supervisión**, selecciona **Métricas**.
2. En **Espacio de nombres de métrica**, elige `governed-ai-gateways`. Si no aparece, todavía no ha llegado ninguna métrica: espera un par de minutos y recarga la página.
3. En **Métrica**, elige `Total Tokens` y, en **Agregación**, **Suma**.
4. Selecciona **Aplicar división** y elige `Subscription ID`. Verás una línea por suscripción de API Management, como `app-basico` y `app-premium`.
5. Cambia la división a `Product ID` para ver el mismo consumo agrupado por producto.
6. Repite con las métricas `Prompt Tokens` y `Completion Tokens`. ¿Qué producto genera más tokens de salida?

Sobre este gráfico pondrías la alerta de la pregunta 2 del paso 5. No la crees: en el taller no se crea ningún recurso desde el portal.

### Seguir la traza en Buscar

1. En **Investigar**, selecciona **Buscar**.
2. Pega el *trace ID* del paso 1 en el cuadro de búsqueda. Verás los elementos de esa operación: la conversación, las tres llamadas `chat gpt-6-luna` y las peticiones que recibió el gateway. Si no aparece nada, en **Tipos de eventos** deja solo **Dependencia** y busca `lab04.conversation`.
3. Selecciona `lab04.conversation` para abrir **Detalles de la transacción de un extremo a otro**.
4. Recorre el diagrama de Gantt de arriba abajo: `lab04.conversation`, del rol `workshop-lab04`, agrupa tres spans `chat gpt-6-luna`; dentro de cada uno está la petición que recibió API Management y, dentro de esta, la llamada al backend `aif-gaig-<entorno>-<sufijo>.services.ai.azure.com`.
5. Selecciona un span `chat gpt-6-luna` y busca, en el panel de propiedades, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` y `workshop.gateway`.
6. Selecciona la petición de API Management. Sus propiedades indican la API, la operación, el producto y la suscripción, pero el gateway no sabe que la llamada forma parte de una conversación de tres preguntas: eso solo lo sabe la aplicación.

### Ver los componentes en el Mapa de aplicación

1. En **Investigar**, selecciona **Mapa de aplicación**.
2. Localiza el nodo `workshop-lab04`, su conexión con el nodo de API Management y la de este con el endpoint de Foundry. Si todavía falta algún nodo, espera un par de minutos y vuelve a cargar el mapa.
3. Selecciona cada nodo y cada conexión para ver el número de llamadas, la duración media y el porcentaje de errores.

### Revisar los rechazos del laboratorio 2 en Errores

1. En **Investigar**, selecciona **Errores**.
2. Cambia el intervalo de tiempo a **Últimas 4 horas** para incluir el tráfico del laboratorio 2.
3. En la pestaña **Operaciones**, revisa en el panel derecho los códigos de respuesta principales. Deberías ver los que provocaste en el laboratorio 2, como `401`, `403` y `429`.
4. Selecciona el código `429` y abre una de sus muestras. En **Detalles de la transacción de un extremo a otro**, las propiedades de la petición indican qué suscripción y qué producto superaron su límite.

### Consultar la telemetría en Registros

Application Insights y el workspace de Log Analytics guardan los mismos datos con nombres distintos. Desde **Registros** de Application Insights se usan las tablas clásicas `requests`, `dependencies` y `customMetrics`; desde el workspace, `AppRequests`, `AppDependencies` y `AppMetrics`, como en las consultas del paso 2. `ApiManagementGatewayLogs` solo está en el workspace.

1. En **Supervisión**, selecciona **Registros**. Cierra la galería de consultas si se abre y, si el editor está en modo simple, cámbialo a **Modo KQL**.
2. Ejecuta esta consulta para ver los tokens de cada llamada desde el lado de la aplicación:

   ```kusto
   dependencies
   | where timestamp > ago(1h) and cloud_RoleName == "workshop-lab04" and name startswith "chat "
   | project timestamp, operation_Id, name, duration,
       model = tostring(customDimensions["gen_ai.response.model"]),
       input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"]),
       output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
   | order by timestamp desc
   ```

3. Ejecuta esta otra para ver los tokens que midió el gateway, por suscripción y producto:

   ```kusto
   customMetrics
   | where timestamp > ago(1h) and name in ("Prompt Tokens", "Completion Tokens", "Total Tokens")
   | extend subscription = tostring(customDimensions["Subscription ID"]), product = tostring(customDimensions["Product ID"])
   | summarize tokens = sum(valueSum) by subscription, product, name
   | order by subscription asc, name asc
   ```

4. Compara ambos resultados: la aplicación cuenta tokens por llamada y conversación; el gateway, por suscripción y producto, para todas las aplicaciones a la vez.

### Explorar la vista Agentes

1. En el menú lateral, selecciona **Agentes (versión preliminar)**.
2. La vista agrupa la telemetría por atributos de agente de las convenciones GenAI, como `gen_ai.agent.name`. El script del laboratorio no es un agente y no los envía, así que es normal que las ejecuciones de agente aparezcan vacías.
3. Revisa el icono **Modelos**. Si recoge las llamadas a `gpt-6-luna`, selecciónalo para abrir la búsqueda filtrada y, desde ella, los detalles de una transacción.

Esta vista cobra sentido cuando tus aplicaciones usan agentes, por ejemplo con Microsoft Agent Framework, que emiten esos atributos.

## Paso 5: reflexionar

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
