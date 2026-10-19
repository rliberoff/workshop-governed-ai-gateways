# Laboratorio 3: AI Gateway de Microsoft Foundry

Duración: 30 minutos.

## Objetivo

Gobernar los modelos desde el propio Foundry con su AI Gateway, en sus dos modos:

- **Independiente**: Foundry crea y gestiona su propia instancia de API Management para la segunda cuenta de Foundry.
- **Integrado**: Foundry se asocia a la instancia de API Management que desplegaste con Terraform, que pasa a alojar a la vez tu API gobernada del laboratorio 2 y la API del AI Gateway.

En ambos casos el AI Gateway usa API Management por debajo. La diferencia es quién es dueño de la instancia y quién define las políticas.

## Qué hay desplegado y qué harás en el portal

La capa `resources` creó dos cuentas de Foundry, cada una con su proyecto y su despliegue de `gpt-6-luna`. Una cuenta admite un único AI Gateway, por eso hacen falta dos para ver ambos modos.

| Modo | Cuenta de Foundry | Proyecto | Instancia de API Management |
| :--- | :--- | :--- | :--- |
| Independiente | `aif-gaig-<entorno>-sa-<hash>` | `proj-gaig-<entorno>-sa` | Nueva, creada por Foundry |
| Integrado | `aif-gaig-<entorno>-<hash>` | `proj-gaig-<entorno>` | `apim-gaig-<entorno>-<hash>`, creada por Terraform |

Habilitar el AI Gateway en una cuenta solo se puede hacer desde el portal de Foundry, en **Manage**, **AI Gateway**; no hay API ni plantilla documentada para ese paso. Es la única excepción del taller a la regla de no tocar el portal. El resultado, en cambio, son recursos normales de Azure: una API compartida para la cuenta, un producto y una suscripción por proyecto en API Management, y enlaces ARM que los unen con la cuenta y el proyecto. Los scripts del laboratorio los descubren siguiendo esos enlaces, sin que tengas que copiar URL ni claves.

Necesitas los roles que ya te dan los requisitos del taller: Owner de la suscripción, o Foundry Owner sobre las cuentas y API Management Service Contributor sobre la instancia.

## Paso 1: crear el AI Gateway independiente

Empieza por aquí: Foundry tarda entre 5 y 10 minutos en aprovisionar la nueva instancia.

1. Abre el [portal de Foundry](https://ai.azure.com) con el interruptor **New Foundry** activado.
2. Selecciona **Manage**, **AI Gateway** y **Add AI Gateway**.
3. Elige la cuenta `aif-gaig-<entorno>-sa-<hash>`.
4. Selecciona **Create new**: Foundry creará una instancia Basic v2 de API Management.
5. Pon como nombre `aigw-gaig-<entorno>`. Es un nombre global; si está ocupado, añade tus iniciales. Si el asistente te pide un grupo de recursos, elige `rg-gaig-<entorno>`.
6. Selecciona **Add**. Mientras el estado sea **Provisioning**, continúa con el paso 2.

## Paso 2: asociar el AI Gateway a tu API Management

1. En **Manage**, **AI Gateway**, selecciona de nuevo **Add AI Gateway**.
2. Elige la cuenta principal, `aif-gaig-<entorno>-<hash>`.
3. Selecciona **Use existing** y elige `apim-gaig-<entorno>-<hash>`. Aparece en la lista porque es un tier v2 de la misma suscripción y tienes permisos sobre ella.
4. Pon como nombre `aigw-gaig-<entorno>-integrado` y selecciona **Add**. Espera a que el estado sea **Enabled**.
5. Selecciona el gateway y, en la lista de proyectos, elige **Add project to gateway** para `proj-gaig-<entorno>`. Los proyectos que ya existían no se añaden solos.
6. Selecciona **Token management**, **+ Set limit**, elige el proyecto `proj-gaig-<entorno>` y el despliegue `gpt-6-luna`, escribe 5.000 tokens por minuto y selecciona **Create**.

Comprueba qué ha creado Foundry en tu instancia:

```powershell
uv run python -m workshop.lab03_foundry_gateway inspeccionar --modo integrado
```

El script sigue el enlace ARM del proyecto hasta su producto en API Management y muestra la API compartida, sus operaciones, la suscripción del proyecto y la URL base que usará el cliente. La lista final de APIs es la clave del modo integrado: `foundry-openai-v1`, la de Terraform, convive con la API que Foundry creó para la cuenta.

Llama al modelo a través del AI Gateway y provoca su límite:

```powershell
uv run python -m workshop.lab03_foundry_gateway llamar --modo integrado
uv run python -m workshop.lab03_foundry_gateway rafaga --modo integrado --peticiones 20
```

Tras varias peticiones aparecen respuestas `429`. El límite lo definiste en Foundry, por proyecto, y lo aplica tu instancia de API Management.

Por último, comprueba que Terraform y Foundry no se pisan:

```powershell
azd provision resources --preview
```

Terraform solo gestiona lo que declara, así que la vista previa no debería proponer cambios por lo que creó Foundry. Si propone alguno, revísalo antes de aplicar nada: lo que creó Foundry se gestiona desde Foundry.

## Paso 3: completar el modo independiente

Cuando el gateway `aigw-gaig-<entorno>` esté **Enabled**:

1. Añade el proyecto `proj-gaig-<entorno>-sa` con **Add project to gateway**.
2. En **Token management**, fija 5.000 tokens por minuto para ese proyecto y su despliegue `gpt-6-luna`.
3. Ejecuta los mismos comandos con el otro modo:

```powershell
uv run python -m workshop.lab03_foundry_gateway inspeccionar --modo independiente
uv run python -m workshop.lab03_foundry_gateway llamar --modo independiente
uv run python -m workshop.lab03_foundry_gateway rafaga --modo independiente --peticiones 20
```

Esta vez la instancia de API Management es la que creó Foundry: solo contiene la API del AI Gateway y no está en el estado de Terraform.

## Paso 4: comparar

| Dimensión | Tu API en API Management (lab 2) | AI Gateway independiente | AI Gateway integrado |
| :--- | :--- | :--- | :--- |
| Dueño de la instancia | Equipo de plataforma | Foundry | Equipo de plataforma |
| Quién define las políticas | Terraform | Administradores de Foundry, en el portal | Foundry para su API y Terraform para la tuya |
| Unidad de gobierno | Producto y suscripción | Proyecto de Foundry | Ambas, en la misma instancia |
| Límites | `llm-token-limit` como código | Token management por proyecto | Ambos |
| Observabilidad | Diagnósticos de Terraform | Los que configures en la nueva instancia | Los de la instancia, que ya envía sus registros a Log Analytics |
| Cuándo encaja | Puerta corporativa con políticas a medida | Un equipo que empieza en Foundry sin equipo de plataforma | Foundry gobernado sobre la puerta corporativa existente |

Reflexiona con tu compañero o compañera:

1. ¿Quién debería ser dueño de la instancia de API Management en tu organización?
2. En el modo integrado, una misma instancia tiene objetos de Terraform y objetos de Foundry. ¿Qué regla pondrías para que nadie gestione un mismo objeto desde dos sitios?
3. ¿Qué ganas y qué pierdes si los equipos de Foundry crean sus propios gateways independientes?

## Limpieza del laboratorio

Antes de eliminar el entorno, en **Manage**, **AI Gateway**, quita los proyectos de los dos gateways y elimina ambos gateways, como recomienda la documentación de Foundry. Al eliminar la capa `resources`, `azd down resources` borra el grupo de recursos completo, incluida la instancia creada por Foundry si está en `rg-gaig-<entorno>`. Si Foundry la creó en otro grupo de recursos, elimínala tú.

## Lo que te llevas

- El AI Gateway de Foundry es API Management gobernado desde Foundry, con límites por proyecto.
- Independiente es la vía rápida; integrado reutiliza la puerta corporativa y su observabilidad.
- Lo que crea Foundry son objetos normales de API Management: se pueden descubrir, auditar y observar como los demás.
