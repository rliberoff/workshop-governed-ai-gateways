# Preparación del entorno

Esta guía deja tu entorno listo para el taller. Te recomendamos completarla **el día anterior**: el despliegue tarda entre 10 y 15 minutos y así aprovecharás todo el tiempo de laboratorio. Si no puedes, lánzalo al inicio de la sesión; avanzará mientras se presentan los conceptos.

## Requisitos

### Cuenta y suscripción de Azure

| Requisito | Por qué |
| :--- | :--- |
| Una suscripción de Azure en la que seas **Owner**, o **Contributor** más **Role Based Access Control Administrator** | Terraform crea asignaciones de roles para las identidades administradas y para ti; Contributor no puede asignar roles |
| Cuota de `gpt-6-luna` GlobalStandard de al menos 60K tokens por minuto en la región | Los despliegues de las dos cuentas de Foundry reservan 50K y 10K |
| Acceso al [portal de Foundry](https://ai.azure.com) con la misma cuenta | En el laboratorio 3 habilitas el AI Gateway de Foundry desde su portal |
| Una región que admita evaluaciones y Red Teaming de Foundry | Recomendamos `swedencentral`, que admite todo lo que usa el taller |

Comprueba la cuota disponible en la región:

```powershell
az cognitiveservices usage list --location swedencentral --query "[?name.value=='OpenAI.GlobalStandard.gpt-6-luna']" --output table
```

El valor de `Limit` menos `CurrentValue` debe ser igual o superior a 60.

Registra los proveedores de recursos que usa el taller si tu suscripción es nueva:

```powershell
foreach ($namespace in "Microsoft.ApiManagement", "Microsoft.CognitiveServices", "Microsoft.OperationalInsights", "Microsoft.Insights", "Microsoft.Storage", "Microsoft.Databricks") {
    az provider register --namespace $namespace
}
```

El registro es idempotente; si un proveedor ya está registrado, el comando no cambia nada.

### Herramientas

| Herramienta | Versión mínima | Comprobación |
| :--- | :--- | :--- |
| Terraform | 1.16.5 | `terraform version` |
| Azure CLI | 2.91.0 | `az version` |
| Azure Developer CLI | 1.36.0 | `azd version` |
| Python | 3.11 a 3.13 | `python --version` |
| uv | 0.10 | `uv --version` |
| Git | Cualquiera reciente | `git --version` |

Python 3.14 no es compatible todavía con PyRIT, la librería que usa el AI Red Teaming Agent. Si tienes varias versiones, `uv` elegirá una compatible.

### Laboratorio opcional de Databricks

Para hacer el laboratorio 6 por tu cuenta necesitas, además:

- Permiso para crear un workspace de Azure Databricks **Premium** en tu suscripción
- Que la cuenta de Databricks de tu organización asigne automáticamente Unity Catalog a los workspaces nuevos (es el comportamiento por defecto de las cuentas creadas después de noviembre de 2023)
- Que el administrador de la cuenta no haya restringido a los administradores de workspace (`RestrictWorkspaceAdmins`)

Si no cumples alguno de estos requisitos, sigue la demostración del instructor: el código es el mismo.

## Paso 1: obtener el repositorio

```powershell
git clone <url-del-repositorio> governed-ai-gateways
Set-Location governed-ai-gateways
```

## Paso 2: autenticarte

Terraform usa la identidad de Azure CLI, así que configuramos `azd` para que use la misma.

```powershell
$tenantId = Read-Host "Tenant ID"
$subscriptionId = Read-Host "Subscription ID"
azd config set auth.useAzCliAuth true
az login --tenant $tenantId
az account set --subscription $subscriptionId
az account show --query "{tenantId:tenantId,id:id,user:user.name}" --output json
```

Comprueba que el tenant y la suscripción que muestra el último comando son los correctos.

## Paso 3: crear tu entorno de azd

El identificador de entorno debe ser único en la suscripción y tener entre 2 y 10 letras minúsculas o dígitos, por ejemplo tus iniciales y un número. Aparece en el nombre de todos tus recursos.

```powershell
$environmentId = Read-Host "Identificador de entorno (2-10 letras minúsculas o dígitos)"
azd env new $environmentId
azd env set AZURE_SUBSCRIPTION_ID $subscriptionId
azd env set AZURE_LOCATION swedencentral
azd env set APIM_PUBLISHER_EMAIL <tu-email>
```

Los valores se guardan en `.azure/<entorno>/.env`, una carpeta local que Git ignora. API Management usa el correo de publicador como contacto y para sus notificaciones.

## Paso 4: desplegar la infraestructura

El proyecto define tres capas en [`azure.yaml`](../azure.yaml). Despliega las dos primeras por separado y revisa siempre la vista previa antes de aplicar.

```powershell
azd provision backend --preview
azd provision backend
```

La capa `backend` crea la cuenta de almacenamiento del estado remoto de Terraform, sin claves compartidas, y te asigna el rol de datos necesario.

```powershell
azd provision resources --preview
azd provision resources
```

La capa `resources` crea dos cuentas de Microsoft Foundry con el modelo, Content Safety, API Management Basic v2, Log Analytics y Application Insights. Tarda entre 10 y 15 minutos, sobre todo por API Management.

No ejecutes `azd provision` sin nombre de capa: desplegaría también la capa opcional de Databricks.

## Paso 5: preparar Python

```powershell
uv sync
```

`uv` crea el entorno virtual `.venv` e instala las versiones exactas de [`uv.lock`](../uv.lock). Si vas a hacer el laboratorio de Databricks, añade el extra correspondiente:

```powershell
uv sync --extra databricks
```

## Paso 6: verificar

```powershell
azd env get-values
uv run python -m workshop.lab01_direct --repeticiones 1
```

El primer comando muestra los valores del entorno, entre ellos `APIM_API_BASE_URL` y `FOUNDRY_PROJECT_ENDPOINT`. El segundo debe responder con `HTTP 200` y un texto del modelo.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
| :--- | :--- | :--- |
| `401` o `403` al inicializar el estado remoto de `resources` | El rol de datos sobre el almacenamiento aún no se ha propagado | Espera hasta 10 minutos, ejecuta `az account get-access-token --output none` y repite la vista previa. No habilites claves compartidas |
| `PermissionDenied` en el laboratorio 1 | El rol Foundry User acaba de asignarse | Espera unos minutos y repite |
| `InsufficientQuota` al crear el despliegue | No hay cuota del modelo en la región | Pide cuota o cambia de región con `azd env set AZURE_LOCATION <región>` antes del primer despliegue |
| Nombre de API Management o de cuenta de Foundry ya en uso | Existe un recurso en borrado temporal con el mismo nombre | Espera a que termine el `azd down` anterior; el provider purga esos recursos al destruirlos |
| `The azd environment has no value for ...` | La capa `resources` no terminó | Ejecuta `azd provision resources` y comprueba que finaliza sin errores |
