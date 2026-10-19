# Laboratorio 1: consumo directo del modelo

Duración: 10 minutos.

## Objetivo

Consumir el modelo desplegado en Microsoft Foundry sin ningún intermediario y detectar qué falta para un uso empresarial. Es el punto de partida que gobernarás en los siguientes laboratorios.

## Qué hay desplegado

La capa `resources` creó una cuenta de Foundry con la autenticación local desactivada: no existen claves de API y solo se aceptan tokens de Microsoft Entra ID. Te asignó el rol **Foundry User** sobre la cuenta, suficiente para invocar el modelo. También creó una segunda cuenta, con el sufijo `-sa`, que usarás en el laboratorio 3 para el AI Gateway independiente de Foundry.

Abre [`inf/resources/modules/aif/main.tf`](../../inf/resources/modules/aif/main.tf) y localiza estos elementos:

- `local_auth_enabled = false` en la cuenta de Foundry
- El despliegue `gpt-6-luna` con SKU `GlobalStandard` y 50K tokens por minuto
- El proyecto, que usarás para evaluaciones, Red Teaming y trazas

## Paso 1: llamar al modelo

```powershell
uv run python -m workshop.lab01_direct
```

El script obtiene un token de Entra ID con tu sesión de Azure CLI y llama tres veces al endpoint OpenAI v1 de Foundry con el SDK oficial de OpenAI. Verás algo parecido a esto:

```text
Endpoint directo: https://aif-gaig-<entorno>-<hash>.openai.azure.com/openai/v1
Modelo: gpt-6-luna

[1] HTTP 200 | 1450 ms | tokens entrada=32 salida=118
    Un AI gateway es un punto de entrada centralizado...
```

## Paso 2: revisar el código

Abre [`src/workshop/clients.py`](../../src/workshop/clients.py) y busca `direct_client`. Solo cambian dos cosas respecto a llamar a OpenAI: la URL base y un proveedor de tokens de Entra ID en lugar de una clave.

## Paso 3: reflexionar

Responde con tu compañero o compañera:

1. Si diez aplicaciones usan este endpoint, ¿cómo sabrías cuántos tokens consume cada una?
2. ¿Qué impide que una sola aplicación agote los 50K tokens por minuto del despliegue?
3. Si una aplicación envía un intento de jailbreak, ¿quién lo detecta y dónde queda registrado?
4. ¿Cómo revocarías el acceso de una aplicación sin afectar a las demás?

Las respuestas honestas son "no lo sé", "nada", "el filtro del despliegue, si lo hay, sin una visión central" y "quitando un rol, uno por uno". El laboratorio 2 cambia esas respuestas.

## Lo que te llevas

- El consumo directo con Entra ID es seguro en cuanto a credenciales, pero no ofrece gobierno por consumidor.
- El mismo SDK de OpenAI sirve para Foundry, para API Management y para Unity Gateway: solo cambia la configuración del cliente.
