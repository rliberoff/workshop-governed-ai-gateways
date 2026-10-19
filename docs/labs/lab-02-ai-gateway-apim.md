# Laboratorio 2: AI gateway con Azure API Management

Duración: 25 minutos.

## Objetivo

Consumir el mismo modelo a través de Azure API Management y aplicar, como código, control de acceso, límites de tokens, resiliencia y seguridad de contenido.

Si vas a hacer el laboratorio opcional de Databricks, lanza ahora su despliegue en otro terminal, porque tarda unos 10 minutos:

```powershell
azd provision databricks --preview
azd provision databricks
```

## Qué hay desplegado

Abre [`inf/resources/modules/apim/main.tf`](../../inf/resources/modules/apim/main.tf). Estas son las piezas del gateway:

| Recurso | Función |
| :--- | :--- |
| `azurerm_api_management` | Instancia Basic v2 con identidad administrada asignada por el sistema |
| `azurerm_role_assignment.apim_foundry_openai_user` | La identidad del gateway puede invocar el modelo; los consumidores no |
| `azurerm_api_management_backend.foundry` | Backend hacia Foundry con un circuit breaker para respuestas 429 y 5xx |
| `azurerm_api_management_api.foundry` | API OpenAI v1 importada desde [`specs/openai-v1.json`](../../inf/resources/modules/apim/specs/openai-v1.json) |
| `azurerm_api_management_api_policy.foundry` | Política de API generada desde [`policies/api.xml.tftpl`](../../inf/resources/modules/apim/policies/api.xml.tftpl) |
| `azurerm_api_management_product` y `_subscription` | Productos `basico` y `premium`, con una suscripción cada uno |
| `azurerm_api_management_product_policy` | Política de producto generada desde [`policies/product.xml.tftpl`](../../inf/resources/modules/apim/policies/product.xml.tftpl) |

## Paso 1: control de acceso

Llama al modelo a través del gateway con la suscripción del producto básico:

```powershell
uv run python -m workshop.lab02_gateway llamar --producto basico
```

El script lee la clave de la suscripción con la API de administración de Azure, usando tu identidad. La clave nunca se escribe en ficheros ni en salidas de Terraform.

Ahora prueba con una clave inventada:

```powershell
uv run python -m workshop.lab02_gateway sin-clave
```

El gateway responde `401` sin llegar a Foundry. Abre la política de API y observa el intercambio de credenciales: `authentication-managed-identity` obtiene un token de la identidad del gateway, `set-header` lo coloca en `Authorization` y la cabecera `api-key` del consumidor se elimina antes de llamar al modelo.

## Paso 2: límites de tokens como código

Las políticas de producto se despliegan desactivadas. Actívalas cambiando una variable del entorno y vuelve a aprovisionar solo la capa `resources`:

```powershell
azd env set APIM_TOKEN_LIMIT_ENABLED true
azd provision resources --preview
azd provision resources
```

En la vista previa solo cambian las dos políticas de producto. El producto `basico` permite 5.000 tokens por minuto y 20.000 al día por suscripción; `premium`, 20.000 por minuto y 1.000.000 al día. Los valores están en la variable `apim_products` de [`inf/resources/variables.tf`](../../inf/resources/variables.tf).

Lanza una ráfaga con cada producto:

```powershell
uv run python -m workshop.lab02_gateway rafaga --producto basico --peticiones 20
uv run python -m workshop.lab02_gateway rafaga --producto premium --peticiones 5
```

Con `basico` aparecerán respuestas `429` tras varias peticiones, con la cabecera `retry-after`. Las respuestas `200` incluyen `x-tokens-consumed`, `x-ratelimit-remaining-tokens` y `x-quota-remaining-tokens`. Con `premium`, todas las peticiones pasan.

| Respuesta | Significado |
| :--- | :--- |
| `429 Too Many Requests` | Se superó `tokens-per-minute`; vuelve a intentarlo tras `retry-after` |
| `403 Forbidden` | Se agotó `token-quota` del periodo |

## Paso 3: seguridad de contenido

Envía dos peticiones dañinas, un intento de jailbreak y una petición violenta, todavía sin la política de contenido:

```powershell
uv run python -m workshop.lab02_gateway seguridad
```

Lo habitual es que el filtro de contenido del despliegue de Foundry rechace la petición violenta con un `400` y que el modelo se niegue a seguir el jailbreak. La protección existe, pero depende de cada despliegue y la petición ya ha llegado al modelo.

Activa `llm-content-safety`, que analiza cada prompt con Azure AI Content Safety y Prompt Shields antes de llamar al modelo:

```powershell
azd env set APIM_CONTENT_SAFETY_ENABLED true
azd provision resources
uv run python -m workshop.lab02_gateway seguridad
```

Ahora el gateway rechaza ambas peticiones con un error del propio gateway, habitualmente `403`: se bloquean antes de consumir tokens del modelo, con la misma regla para cualquier modelo detrás del gateway. Los umbrales por categoría están en la variable `apim_content_safety_thresholds`.

## Paso 4: resiliencia

Revisa en la política de API el bloque `retry` de la sección `backend` y, en `main.tf`, el `circuit_breaker_rule` del backend:

- El gateway reintenta hasta dos veces las respuestas `429` y `5xx` del modelo.
- Si el modelo devuelve tres respuestas de ese tipo en un minuto, el circuito se abre durante un minuto y el gateway responde `503` de inmediato, respetando `Retry-After`. Así protege al modelo saturado y a los consumidores.

En producción se combina con un *backend pool* que reparte el tráfico entre varios despliegues o regiones.

## Reto opcional

Sube el límite del producto `basico` a 10.000 tokens por minuto editando el valor por defecto en `inf/resources/variables.tf`, revisa la vista previa, aprovisiona y repite la ráfaga. En un equipo real este cambio llegaría mediante una pull request revisada: es gobierno como código.

## Lo que te llevas

- El consumidor solo conoce una clave de suscripción revocable; el gateway es el único que habla con el modelo.
- Los límites y la seguridad de contenido son políticas declarativas, versionadas y desplegadas con Terraform y `azd`.
- Bloquear en el gateway ahorra tokens y aplica la misma regla a todos los modelos.
