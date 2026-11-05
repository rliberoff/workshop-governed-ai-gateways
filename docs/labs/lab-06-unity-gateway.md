# Laboratorio 6: Databricks Unity Gateway

Duración: 15 minutos. para quien tenga desplegada la capa `databricks`.

## Objetivo

Gobernar el mismo despliegue de Foundry desde Azure Databricks con Unity Gateway, comparar su modelo de gobierno con el de API Management y ver su tabla unificada de trazas en formato OpenTelemetry.

La demostración del instructor y tu laboratorio usan exactamente el mismo código Terraform y Python. La demostración requiere además permisos sobre las tablas de sistema y la habilitación de la tabla unificada de trazas por un administrador del metastore; desplegar la capa `databricks` no concede esos permisos ni habilita esa tabla.

## Requisitos

- La capa `databricks` desplegada con `azd provision databricks`, lanzada durante el laboratorio 2
- Las dependencias de Databricks instaladas con `uv sync --extra databricks`

Terraform mantiene el acceso administrativo del desplegador al workspace, pero no intenta concederle permisos sobre el catálogo compartido `system` por defecto. La variable `manage_system_usage_grants` vale `false`; consultar `system.ai_gateway.usage` requiere que un administrador autorice el acceso por separado, como se explica en la demostración del instructor.

## Preparación desde cero, sin metastore previo

Este es el punto de partida para la primera instalación: no existe todavía un metastore de Unity Catalog en la región del taller. No necesitas conservar un workspace anterior ni conocer el ID de un metastore antiguo. El objetivo es dejar preparados tanto los pasos 1 a 4 como la demostración de uso y trazas; haz esta preparación el día anterior, no dentro de los 15 minutos del laboratorio.

### Preparar las identidades de administración

Necesitas los permisos de Azure de la [guía de preparación](../00-preparacion.md) y un **Account admin de Databricks** para la configuración inicial. Ser Owner de la suscripción o iniciar sesión en Azure CLI no te concede ese rol de Databricks.

Si la cuenta de Databricks aún no tiene ningún administrador, un Global Administrator de Microsoft Entra ID debe realizar el primer acceso a la [consola de cuenta de Azure Databricks](https://accounts.azuredatabricks.net). Puede delegar después el rol Account admin al responsable del taller; los administradores delegados no necesitan ser Global Administrator. Comprueba el tenant y la cuenta de Databricks antes de continuar.

Las operaciones de consola de esta preparación requieren autorización explícita del responsable de la cuenta cuando no las gestiona su infraestructura como código. La excepción puntual para asignar el administrador del metastore no autoriza cambios generales en la cuenta ni sustituye la política de Terraform del repositorio.

### Crear el primer workspace y el metastore

1. Completa los pasos 1 a 5 de la [guía de preparación](../00-preparacion.md): autentícate, crea un entorno nuevo de `azd` y despliega `backend` y `resources`, revisando sus vistas previas. En una instalación nueva usa `azd env new`, no selecciones un entorno anterior.
2. Confirma que la cuenta permite la habilitación automática de Unity Catalog para workspaces nuevos. Este es el mecanismo que utiliza el taller: al crear el primer workspace Premium en una región sin metastore, Databricks puede aprovisionar el metastore regional y asociarlo al workspace. No lo crea un recurso `databricks_metastore` de este repositorio.
3. Desde la raíz del repositorio, instala el extra y despliega la capa opcional. Revisa la vista previa antes de aplicar.

```powershell
uv sync --extra databricks
azd provision databricks --preview
azd provision databricks
```

La capa crea el workspace, resuelve su catálogo y configura el servicio de Unity Gateway. El metastore y el catálogo deben estar disponibles para que termine. Si no aparecen inmediatamente, espera a que termine el alta de Unity Catalog y repite la vista previa antes de reintentar.

Si la cuenta no realiza esa habilitación automática, este Terraform no cubre por sí solo el arranque: el Account admin debe preparar el metastore y su asociación mediante un despliegue de cuenta autorizado, antes de completar la capa. La [creación explícita de un metastore](https://learn.microsoft.com/azure/databricks/data-governance/unity-catalog/create-metastore) admite Terraform y distingue el almacenamiento raíz opcional de los requisitos de almacenamiento de los catálogos. No basta con crear un metastore vacío: también hacen falta asociación, catálogo utilizable y permisos. No inventes una ruta ADLS ni elijas otro catálogo al azar para hacer pasar el despliegue. Esta alternativa requiere ampliar la infraestructura; no está implementada en la capa actual.

Obtén la URL y los nombres efectivos sin mostrar el resto de la configuración:

```powershell
$values = azd env get-values --output json | ConvertFrom-Json
$values | Select-Object DATABRICKS_WORKSPACE_URL, DATABRICKS_WORKSPACE_RESOURCE_ID, DATABRICKS_MODEL_PROVIDER_SERVICE, DATABRICKS_SCHEMA
```

### Asignar el administrador inicial del metastore

La habilitación automática de Unity Catalog no implica que el desplegador sea administrador del metastore. Es una asignación distinta del acceso administrativo al workspace que mantiene Terraform.

1. Como Account admin, abre **Catalog** en la consola de cuenta y localiza el metastore de la misma región que el workspace recién creado. Solo puede existir un metastore por región y cuenta; no crees uno por asistente.
2. Comprueba las asociaciones de workspaces y anota el ID del metastore. En una instalación realmente nueva no estás recuperando el ID de otra instalación.
3. Con la autorización indicada al principio de esta sección, abre **Metastore Admin**, **Edit**, selecciona el usuario o grupo responsable del taller y pulsa **Save**. Databricks recomienda un grupo; asegúrate de que el instructor pertenece a él. No basta con darle administración del workspace.
4. Si el metastore ya tiene un administrador definido, verifica si esa asignación te da acceso antes de cambiarla. Un UUID no demuestra que la identidad esté eliminada. Sustituirla requiere autorización y afecta a todos los workspaces asociados, no solo al taller.
5. Espera al menos 30 segundos y actualiza el workspace; la propagación puede tardar más. Mantén `manage_system_usage_grants = false` para la instalación normal.

El instructor que reúne Account admin y Metastore admin tiene acceso predeterminado a las tablas de sistema. Para asistentes que necesiten consultar `usage`, un administrador concede únicamente los permisos descritos en [permisos del catálogo de sistema](#permisos-del-catálogo-de-sistema). No hagas administradores del metastore a todos los asistentes.

### Comprobar Unity Catalog y los permisos

1. Abre la URL nueva de `DATABRICKS_WORKSPACE_URL`, no un marcador del workspace eliminado. Verifica tu acceso administrativo al workspace.
2. En la consola de cuenta, abre **Catalog**, selecciona el metastore de la región y comprueba su ID, el administrador y las asociaciones de workspaces. No presupongas que el ID nuevo sustituye automáticamente al anterior. Si falta la asociación, el administrador de cuenta debe resolverla mediante la gestión de infraestructura autorizada antes de continuar; este Terraform no declara esa asignación.
3. En el workspace nuevo, abre **SQL Editor** y selecciona un SQL warehouse serverless al que tengas acceso. Si no existe ninguno utilizable, el administrador del workspace debe aprovisionarlo por la vía autorizada; desplegar esta capa no lo crea.
4. Ejecuta la comprobación de identidad y metastore siguiente y contrasta el resultado con la consola de cuenta.

```sql
SELECT current_user() AS user_name,
       current_metastore() AS metastore_id;
```

El segundo valor incluye nube, región e ID del metastore. Ni un warehouse serverless ni el rol de administrador del workspace te convierten en administrador del metastore.

Si mantienes los roles de administrador de cuenta y de metastore, prueba directamente la [consulta de uso](#permisos-del-catálogo-de-sistema): tienes acceso predeterminado a las tablas de sistema. Para otros usuarios, un administrador autorizado debe verificar o restaurar `USE CATALOG`, `USE SCHEMA` y `SELECT`. Mantén `manage_system_usage_grants = false` salvo que hayas decidido gestionar esas concesiones con una identidad ya autorizada.

Si falta un administrador accesible, no repitas concesiones desde la identidad que ya devuelve `MANAGE` insuficiente. La recuperación excepcional requiere autorización explícita del responsable de la cuenta: un Account admin abre **Catalog**, el metastore, **Metastore Admin**, **Edit**, selecciona el usuario o grupo aprobado y pulsa **Save**. Se recomienda un grupo. Esa operación sustituye al administrador actual y afecta a todos los workspaces asociados; no es una operación ordinaria del taller ni una excepción general a Terraform. Espera al menos 30 segundos, actualiza el workspace y vuelve a comprobar el acceso; la propagación puede tardar más. No cambies al administrador si la asignación existente ya te da acceso.

## Qué hay desplegado

Abre [`inf/databricks/main.tf`](../../inf/databricks/main.tf):

| Recurso | Función |
| :--- | :--- |
| `azurerm_databricks_workspace` | Workspace Premium con Unity Catalog habilitado automáticamente |
| `azurerm_role_assignment.deployer_workspace_contributor` | Acceso administrativo del desplegador limitado al workspace, mediante autenticación de Azure |
| `databricks_grant.deployer_*` | Opcional: lectura de `system.ai_gateway.usage`; solo se gestiona con `manage_system_usage_grants = true` y autorización previa |
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

En el workspace de Databricks, abre el **SQL Editor** con un SQL warehouse serverless. `DATABRICKS_SCHEMA` contiene catálogo y esquema; añade solo `.foundry_payload` para obtener el nombre completo. Puedes obtenerlo sin mostrar el resto de la configuración:

```powershell
$values = azd env get-values --output json | ConvertFrom-Json
"$($values.DATABRICKS_SCHEMA).foundry_payload"
```

Pega el resultado, en el parámetro **String** `payload_table` que aparece al introducir esta consulta entre comillas simples:

```sql
SELECT *
FROM IDENTIFIER(:payload_table)
LIMIT 10;
```

Por ejemplo:

```sql
SELECT *
FROM IDENTIFIER('some_catalog.ai_gateway.foundry_payload')
LIMIT 10;
        
```

Las filas pueden tardar unos minutos en aparecer. Contienen la petición, la respuesta y metadatos como las etiquetas de la petición.

## Paso 4: comparar todos los caminos

```powershell
uv run python -m workshop.lab06_unity_gateway comparar
```

El mismo prompt viaja por Foundry directo, tu API en API Management, el AI Gateway de Foundry en sus dos modos y Unity Gateway. Todos usan el mismo modelo; el modo independiente usa el despliegue de la segunda cuenta de Foundry y el resto, el de la cuenta principal. Compara latencias, cabeceras y quién aplica cada política. Si no desplegaste la capa `databricks` o algún AI Gateway de Foundry, el script omite ese camino y lo indica.

## Demostración del instructor

Esta demostración es independiente del comando `comparar` del paso 4. Si no tienes los permisos o las funcionalidades indicadas, puedes completar los pasos 1 a 4 y dejar esta sección al instructor.

No intercambies estas tres tablas: tienen estructuras y requisitos distintos.

| Tabla | Contenido | Configuración |
| :--- | :--- | :--- |
| `foundry_payload`, en el catálogo del taller y esquema `ai_gateway` | Peticiones, respuestas y metadatos del servicio | Inference table configurada por Terraform; se consulta en el paso 3 |
| `system.ai_gateway.usage` | Uso, tokens, solicitante, estado HTTP y latencia | Tabla de sistema con permisos independientes |
| Tabla unificada de trazas | Spans OpenTelemetry, con `trace_id`, `parent_span_id`, `status` y `attributes` | Beta habilitada y configurada por administradores |

### Permisos del catálogo de sistema

El error `cannot create grant: User does not have MANAGE on Catalog 'system'` durante el despliegue significa que la identidad intenta gestionar concesiones para las que no está autorizada. Ser administrador del workspace no concede administración de la cuenta ni del metastore. Mantén `manage_system_usage_grants = false` para el despliegue normal; no necesitas `MANAGE` sobre `system` para ejecutar los pasos 1 a 4.

Activa `manage_system_usage_grants = true` solo en ejecuciones Terraform cuya identidad ya esté autorizada para gestionar las tres concesiones. Esta opción es autoritativa para los privilegios directos del desplegador sobre esos objetos y no sustituye los de otros usuarios. Si las concesiones ya están en el estado, desactivar la opción propone revocarlas: revisa la previsualización y no apliques revocaciones inesperadas. El cambio no concede privilegios administrativos adicionales ni elude los controles de Unity Catalog.

Un administrador que tenga tanto el rol de administrador de cuenta como el de administrador del metastore debe revisar y conceder el acceso:

1. En **Catalog**, selecciona el catálogo `system` y abre **Permissions**, **Grant**. Selecciona el usuario o grupo autorizado y concede `USE CATALOG`.
2. Selecciona el esquema `system.ai_gateway` y, desde **Permissions**, **Grant**, concede `USE SCHEMA` al mismo usuario o grupo.
3. Selecciona la tabla `system.ai_gateway.usage` y, desde **Permissions**, **Grant**, concede `SELECT` al mismo usuario o grupo. No es necesario conceder lectura sobre todo el catálogo `system`.

Después, abre el **SQL Editor**, selecciona un SQL warehouse y ejecuta esta consulta de uso:

```sql
SELECT event_time, service_name, requester, status_code, total_tokens, latency_ms
FROM system.ai_gateway.usage
WHERE event_time >= current_timestamp() - INTERVAL 1 DAY
ORDER BY event_time DESC
LIMIT 50;
```

Los registros suelen tardar hasta una hora en estar disponibles, y más en workspaces nuevos. Esta tabla no tiene las columnas de spans de la consulta siguiente: conceder permisos no convierte `usage` en una tabla de trazas.

## Referencias

- [Seguimiento del uso](https://learn.microsoft.com/azure/databricks/ai-gateway/usage-tracking)
- [Permisos sobre tablas de sistema](https://learn.microsoft.com/azure/databricks/admin/system-tables/#grant-access-to-system-tables)
- [Administración del metastore](https://learn.microsoft.com/azure/databricks/data-governance/unity-catalog/manage-metastore)
- [Roles administrativos de Unity Catalog](https://learn.microsoft.com/azure/databricks/data-governance/unity-catalog/manage-privileges/admin-privileges)
- [Tabla unificada de trazas](https://learn.microsoft.com/azure/databricks/ai-gateway/unified-trace-table)
- [Parámetros del editor SQL](https://learn.microsoft.com/azure/databricks/sql/user/queries/query-parameters)

## Lo que te llevas

- Unity Gateway gobierna con privilegios de Unity Catalog: el acceso a un modelo se concede igual que el acceso a una tabla.
- La service credential evita copiar secretos de Foundry en Databricks.
- La tabla unificada de trazas lleva la actividad de IA a una tabla OpenTelemetry consultable con SQL, junto a los datos.
