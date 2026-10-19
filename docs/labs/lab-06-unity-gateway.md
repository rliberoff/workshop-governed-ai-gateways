# Laboratorio 6: Databricks Unity Gateway

Duración: 15 minutos: 7 de demostración del instructor y 8 de laboratorio para quien tenga desplegada la capa `databricks`.

## Objetivo

Gobernar el mismo despliegue de Foundry desde Azure Databricks con Unity Gateway, comparar su modelo de gobierno con el de API Management y ver su tabla unificada de trazas en formato OpenTelemetry.

La demostración del instructor y tu laboratorio usan exactamente el mismo código Terraform y Python. La única diferencia es la configuración de la tabla unificada de trazas, que requiere ser administrador del metastore.

## Requisitos

- La capa `databricks` desplegada con `azd provision databricks`, lanzada durante el laboratorio 2
- Las dependencias de Databricks instaladas con `uv sync --extra databricks`

## Qué hay desplegado

Abre [`inf/databricks/main.tf`](../../inf/databricks/main.tf):

| Recurso | Función |
| :--- | :--- |
| `azurerm_databricks_workspace` | Workspace Premium con Unity Catalog habilitado automáticamente |
| `azurerm_databricks_access_connector` | Identidad administrada con el rol Cognitive Services OpenAI User sobre Foundry |
| `databricks_credential.foundry` | *Service credential* de Unity Catalog que usa esa identidad: ninguna clave de Foundry |
| `databricks_schema.ai_gateway` | Esquema que agrupa los objetos de Unity Gateway y la *inference table* |
| `databricks_ai_gateway_model_provider_service.foundry` | Punto de entrada gobernado al despliegue de Foundry, con un límite de 5.000 tokens por minuto por usuario e inference table |

El límite de tokens coincide con el del producto `basico` de API Management para que puedas comparar ambos gateways.

## Paso 1: llamar a través de Unity Gateway

```powershell
uv run python -m workshop.lab06_unity_gateway llamar
```

El cliente usa la misma clase `OpenAI` que en los laboratorios anteriores. Cambian la URL base, que es la ruta `/ai-gateway/openai/v1` del workspace; la credencial, un token de Databricks obtenido con tu sesión de Azure CLI; y la cabecera `Databricks-Model-Provider-Service`, que selecciona el servicio. Revisa `unity_gateway_client` en [`src/workshop/clients.py`](../../src/workshop/clients.py): también envía la cabecera `Databricks-Ai-Gateway-Request-Tags` para atribuir el consumo.

## Paso 2: provocar el límite de tokens

```powershell
uv run python -m workshop.lab06_unity_gateway rafaga --peticiones 20
```

Tras varias peticiones aparecen respuestas `429`. El límite lo aplica Unity Catalog por usuario, no por clave de suscripción.

## Paso 3: consultar la inference table

En el workspace de Databricks, abre el **SQL Editor** con un SQL warehouse serverless y consulta la tabla de cargas del servicio, sustituyendo el catálogo por el valor de `DATABRICKS_SCHEMA` de `azd env get-values`:

```sql
SELECT *
FROM <catalogo>.ai_gateway.foundry_payload
LIMIT 10;
```

Las filas pueden tardar unos minutos en aparecer. Contienen la petición, la respuesta y metadatos como las etiquetas de la petición.

## Paso 4: comparar todos los caminos

```powershell
uv run python -m workshop.lab06_unity_gateway comparar
```

El mismo prompt viaja por Foundry directo, tu API en API Management, el AI Gateway de Foundry en sus dos modos y Unity Gateway. Todos usan el mismo modelo; el modo independiente usa el despliegue de la segunda cuenta de Foundry y el resto, el de la cuenta principal. Compara latencias, cabeceras y quién aplica cada política. Si no desplegaste la capa `databricks` o algún AI Gateway de Foundry, el script omite ese camino y lo indica.

## Demostración del instructor

El instructor muestra lo que requiere privilegios de administrador de cuenta o de metastore:

1. La tabla de sistema `system.ai_gateway.usage`, con el uso por servicio, solicitante y latencia de todos los asistentes.
2. La configuración de la **tabla unificada de trazas** (Beta): en **AI Gateway**, **Govern**, **Traces**, **Set up tracing**, eligiendo catálogo y esquema.
3. Consultas sobre la tabla de trazas, que usa el esquema de spans de OpenTelemetry:

   ```sql
   SELECT trace_id, name, status.code, attributes:`http.response.status_code`::int AS status_code
   FROM <catalogo>.<esquema>.<tabla_de_trazas>
   WHERE parent_span_id IS NULL
     AND time >= current_timestamp() - INTERVAL 1 HOUR;
   ```

   Como el cliente del taller propaga `traceparent`, los spans del gateway se unen al contexto de traza que inició el script. La ingesta de spans propios de la aplicación en esta tabla está en Beta y se habilita por workspace a petición.

## Lo que te llevas

- Unity Gateway gobierna con privilegios de Unity Catalog: el acceso a un modelo se concede igual que el acceso a una tabla.
- La service credential evita copiar secretos de Foundry en Databricks.
- La tabla unificada de trazas lleva la actividad de IA a una tabla OpenTelemetry consultable con SQL, junto a los datos.
