# Guía del instructor

Taller introductorio de 180 minutos para perfiles de desarrollo, arquitectura y plataforma que empiezan a llevar IA generativa a entornos empresariales. No requiere experiencia previa con API Management ni con Databricks; sí ayuda conocer Azure y la línea de comandos.

## Mensajes clave

1. Construir con IA es fácil; gobernarla es el reto empresarial.
2. Un AI gateway resuelve una vez, en un punto común, el acceso, el consumo, la seguridad y la trazabilidad.
3. API Management, Microsoft Foundry y Unity Gateway no compiten: cada uno gobierna un tipo de consumo y pueden convivir sobre el mismo modelo; el AI Gateway de Microsoft Foundry incluso puede vivir dentro de la instancia corporativa de API Management.
4. El gobierno es código: políticas, límites y permisos se versionan y se despliegan con herramientas de Infraestructura como Código (IaC, Infrastructure as Code) tales como Bicep, Terraform, Pulumi y líneas de comando (CLI, Command Line Interface) tales como `az` y`azd`.
5. Antes de producción se ataca y se evalúa; después, se observa.

## Preparación

### Un tiempo antes del taller

- Confirma la región. Se propone `swedencentral`; esta región admite el modelo, las evaluaciones, el AI Red Teaming Agent, Unity Gateway y los modelos externos de Databricks. Hay más regiones disponibles según la documentación de cada servicio.
- Confirma que cada asistente tendrá una suscripción con rol Owner o equivalente y cuota de `gpt-6-luna`. Si comparten suscripción, cada uno necesita un identificador de entorno distinto y la suma de cuotas debe caber: 60K tokens por minuto por asistente, repartidos entre sus dos cuentas de Microsoft Foundry.
- Para el laboratorio opcional de Databricks, confirma con el administrador de la cuenta de Databricks que los workspaces nuevos reciben Unity Catalog automáticamente y que los administradores de workspace no están restringidos.
- Envía a los asistentes la [guía de preparación](00-preparacion.md) y pídeles que desplieguen la víspera.

### El día anterior

- Despliega tu entorno completo, incluida la capa `databricks`, y ejecuta todos los laboratorios una vez, incluidos los dos modos del AI Gateway de Microsoft Foundry del laboratorio 3. Anota cuánto tarda Microsoft Foundry en crear la instancia del modo independiente y dónde la crea: así sabrás qué decir a los asistentes.
- Deja activadas `APIM_TOKEN_LIMIT_ENABLED` y `APIM_CONTENT_SAFETY_ENABLED` en un segundo entorno de respaldo, para mostrar resultados si algo falla en directo.
- Como administrador del metastore, configura la tabla unificada de trazas en **AI Gateway**, **Govern**, **Traces**, **Set up tracing**. Verifica que tu región dispone de Zerobus Ingest, que es requisito de esta tabla.
- Ejecuta un escaneo de Red Teaming de cada camino y guarda los JSON para enseñarlos si el escaneo en directo tarda.

### Antes de empezar

- Abre en pestañas: el repositorio, el portal de Microsoft Foundry con tu proyecto, el workspace de Log Analytics, Application Insights y el workspace de Databricks con el SQL Editor.
- Ten los terminales con el entorno `azd` seleccionado y `uv sync --extra databricks` ejecutado.

## Guion

| Minuto | Bloque | Qué hacer | Mensaje |
| :--- | :--- | :--- | :--- |
| 0-15 | Bienvenida | Presenta objetivos y agenda. Pide a quien no haya desplegado que lance ya `azd provision backend` y `azd provision resources` | El despliegue avanza mientras hablamos |
| 15-35 | Conceptos | Presenta los retos, qué es un AI gateway y la comparativa de [conceptos](01-conceptos.md) | Tres tecnologías, un mismo objetivo |
| 35-45 | Lab 1 | Ejecuta el script en directo y lanza las cuatro preguntas de reflexión | Seguro en credenciales no significa gobernado |
| 45-70 | Lab 2 | Recorre `modules/apim/main.tf` antes de ejecutar. Recuerda a quien haga Databricks que lance `azd provision databricks` | El gateway es el único que habla con el modelo |
| 70-100 | Lab 3 | Haz el paso 1 en pantalla con todos a la vez, para que el modo independiente se aprovisione mientras hacéis el integrado | El mismo AI Gateway, con APIM propio o con el corporativo |
| 100-110 | Descanso | Atiende incidencias de despliegue y de AI Gateways pendientes | |
| 110-130 | Lab 4 | Mientras llega la ingesta, explica la tabla de señales del laboratorio | Medir en el gateway es medir igual para todos |
| 130-155 | Lab 5 | Lanza los dos escaneos en paralelo y, mientras corren, la evaluación | Atacar y evaluar son pruebas automatizables |
| 155-170 | Lab 6 | Demostración de 7 minutos y laboratorio opcional | Gobernar el modelo como se gobiernan los datos |
| 170-180 | Cierre | [Arquitectura integrada](02-arquitectura-integrada.md), checklist de producción y limpieza | Seguro, gobernado, observable y evaluable |

### Sobre el AI Gateway de Microsoft Foundry

El [laboratorio 3](labs/lab-03-ai-gateway-foundry.md) es la única excepción a la regla de no tocar el portal: habilitar el AI Gateway en una cuenta de Microsoft Foundry solo está documentado desde **Manage**, **AI Gateway**. Insiste en tres ideas:

1. Por debajo siempre hay API Management. En el modo independiente Microsoft Foundry crea una instancia Basic v2; en el integrado reutiliza la instancia corporativa, la de Terraform.
2. Lo que crea Microsoft Foundry son objetos normales de API Management (una API compartida para la cuenta y, por proyecto, un producto y una suscripción) unidos a la cuenta y al proyecto con enlaces ARM. El script `inspeccionar` los descubre siguiendo esos enlaces.
3. En el modo integrado conviven objetos de dos dueños en la misma instancia. Terraform no toca lo que no declara; la regla es que cada objeto se cambie solo desde su dueño.

Cuando enseñes `inspeccionar --modo integrado`, señala la lista de APIs: la de Terraform y la de Microsoft Foundry, una al lado de la otra.

### Demostración de Databricks

1. En `inf/databricks/main.tf`, muestra la service credential y el model provider service: no hay ninguna clave.
2. Ejecuta `uv run python -m workshop.lab06_unity_gateway comparar` para ver todos los caminos, incluidos los dos modos del AI Gateway de Microsoft Foundry.
3. En el SQL Editor, consulta `system.ai_gateway.usage`, que requiere ser administrador de cuenta y de metastore, filtrando por `service_name` para ver el uso de todos los asistentes.
4. Consulta la tabla unificada de trazas con las consultas del [laboratorio 6](labs/lab-06-unity-gateway.md) y busca el `trace_id` de una llamada recién hecha.

## Plan B

| Situación | Alternativa |
| :--- | :--- |
| Un asistente no puede desplegar por permisos o cuota | Trabaja en pareja con otro asistente durante los laboratorios |
| API Management tarda más de 20 minutos | Continúa con el laboratorio 1, que solo necesita Microsoft Foundry, y retoma el 2 cuando termine |
| La ingesta de registros tarda | Enseña las consultas en tu entorno, que ya tiene datos del día anterior |
| El escaneo de Red Teaming no termina a tiempo | Enseña los JSON guardados el día anterior y deja el escaneo corriendo |
| La red del aula bloquea `*.azure-api.net` o `*.azuredatabricks.net` | Usa tu entorno en pantalla compartida; los asistentes siguen el código |
| El AI Gateway independiente sigue en **Provisioning** al acabar el paso 2 | Continúa con el resto del laboratorio y completa el paso 3 en el descanso |
| La instancia de Terraform no aparece en **Use existing** | Comprueba que el asistente tiene Owner o API Management Service Contributor sobre ella y que es la misma suscripción; si persiste, que la asocie su compañero en pantalla compartida |
| `inspeccionar` dice que el proyecto no está en el gateway | Falta **Add project to gateway** para el proyecto que ya existía |
| Las llamadas al AI Gateway devuelven `500` justo después de habilitarlo | Espera unos minutos a que terminen de aprovisionarse los objetos de API Management y repite |
| La capa `databricks` falla al leer el catálogo | Espera un par de minutos a que el workspace termine de crear su catálogo y repite `azd provision databricks` |

## Preguntas frecuentes

**¿Por qué Basic v2 y no Consumption?** Las políticas `llm-token-limit` y `llm-emit-token-metric` no están disponibles en Consumption, y el AI Gateway de Microsoft Foundry solo admite instancias v2.

**¿Por qué una cuenta de Content Safety separada?** La política `llm-content-safety` necesita un backend de Azure AI Content Safety con identidad administrada; una cuenta dedicada aísla su uso y sus permisos.

**¿Por qué usar el proveedor `azapi` en algunos recursos?** El proveedor `azurerm` no expone todavía las credenciales de identidad administrada de los backends, la propiedad `metrics` del diagnóstico de Application Insights, las métricas personalizadas con dimensiones de Application Insights ni las conexiones a nivel de proyecto de Microsoft Foundry. Cada uso del proveedor `azapi` está comentado en el código.

**¿Hay que activar algo en el portal para `llm-emit-token-metric`?** No. La documentación indica activar **Custom metrics (Preview)**, **With dimensions** en Application Insights; Terraform aplica ese mismo ajuste con la propiedad `CustomMetricsOptedInType`. Puedes comprobarlo en el portal, en **Usage and estimated costs**, sin cambiar nada.

**¿Por qué hay dos cuentas de Microsoft ?** Una cuenta admite un único AI Gateway. Para practicar los dos modos, la cuenta principal se asocia a la instancia de Terraform y la segunda, con sufijo `-sa`, recibe un gateway independiente. La segunda cuenta despliega el mismo modelo con solo 10K tokens por minuto.

**¿Por qué no se asocia el AI Gateway con Terraform?** La documentación de Microsoft Foundry solo describe el portal para habilitar el gateway en una cuenta. La plantilla oficial `project-ai-gateway` de `microsoft-foundry/foundry-samples` sí habilita proyectos por código, pero exige una cuenta que ya tenga gateway. Cuando exista una vía declarativa para la cuenta, este laboratorio debería pasar a Terraform.

**¿Es lo mismo que *Bring your own model*?** No. El AI Gateway de Microsoft Foundry gobierna los modelos de Microsoft Foundry desde Microsoft Foundry. *Bring your own model* es la dirección contraria: los agentes de Microsoft Foundry consumen modelos que están detrás de tu propio gateway, mediante una conexión de tipo `ApiManagement` o `ModelGateway` que sí se despliega por código.

**¿Las claves de suscripción están en el estado de Terraform?** El estado remoto vive en una cuenta de almacenamiento sin claves compartidas y con acceso por RBAC. Los scripts nunca leen las claves del estado: las obtienen en el momento con la API de administración.

**¿Por qué el F1 sale bajo?** Mide solapamiento de palabras con la respuesta de referencia; una respuesta correcta con otras palabras puntúa bajo. Por eso se combina con evaluadores asistidos por IA.

**¿Puede Unity Gateway llamar a API Management en lugar de a Microsoft Foundry?** Sí, registrando API Management como proveedor personalizado con autenticación por cabecera. Encadenar gateways centraliza la cuota corporativa, a cambio de latencia y doble registro. El taller conecta ambos gateways directamente al modelo para compararlos.

## Costes

El taller usa servicios de pago por uso y servicios facturados por hora mientras existen, sobre todo API Management Basic v2. Los tokens del modelo, Content Safety, la ingesta en Log Analytics, el SQL warehouse serverless y el registro de uso de Unity Gateway se facturan por consumo. Estima el coste de tu número de asistentes con la [calculadora de precios de Azure](https://azure.microsoft.com/pricing/calculator/) y recuerda la limpieza.

## Limpieza

Al final de la sesión, pide a cada asistente que ejecute `azd down` de cada capa en orden inverso, como indica la [arquitectura integrada](02-arquitectura-integrada.md). Comprueba que no quedan grupos de recursos del taller:

```powershell
az group list --query "[?tags.project=='gaig'].name" --output table
```

El comando lista los grupos de recursos con la etiqueta `project=gaig` que siguen existiendo en la suscripción.
