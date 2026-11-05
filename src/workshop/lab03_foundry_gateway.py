"""Lab 3: the Foundry AI Gateway, standalone and associated with the API Management instance of the workshop."""

from __future__ import annotations

import argparse

from workshop.chat import chat, describe
from workshop.config import load_settings
from workshop.foundry_gateway import MODES, discover, gateway_client, list_service_apis
from workshop.lab02_gateway import LONG_PROMPT, SHORT_PROMPT

# The API that Terraform created in the resources layer, to tell it apart from the APIs that Foundry creates.
TERRAFORM_API_NAME = "foundry-openai-v1"


def inspect(mode: str) -> None:
    settings = load_settings()
    artifacts = discover(settings, mode)

    print(f"== AI Gateway de Foundry ({mode}) ==")
    print(f"Proyecto:            {artifacts.project_name}")
    print(f"API Management:      {artifacts.apim_name} ({artifacts.apim_resource_group})")
    print(f"Producto del proyecto: {artifacts.product_name}")
    print(f"Suscripción:         {artifacts.subscription_name}")
    print(f"API compartida:      {artifacts.api_name} (ruta /{artifacts.api_path})")
    print(f"Cabecera de la clave: {artifacts.key_header}")
    print(f"URL base del proyecto: {artifacts.base_url}")
    if artifacts.api_version:
        print(f"api-version:         {artifacts.api_version}")

    print("\nOperaciones de la API compartida:")
    for method, template in artifacts.operations:
        print(f"  {method:6} {template}")

    print(f"\nAPIs de la instancia {artifacts.apim_name}:")
    for name, path in list_service_apis(artifacts):
        if name == TERRAFORM_API_NAME:
            origin = "Terraform (laboratorio 2)"
        elif name == artifacts.api_name:
            origin = "AI Gateway de Foundry"
        else:
            origin = "otra"
        print(f"  {name:40} /{path:30} {origin}")

    if artifacts.apim_name == settings.apim_name:
        print("\nLa instancia es la de Terraform: tu API gobernada y la del AI Gateway de Foundry conviven en ella.")
    else:
        print("\nLa instancia la creó Foundry: no está en el estado de Terraform.")


def call(mode: str) -> None:
    settings = load_settings()
    artifacts = discover(settings, mode)
    client = gateway_client(artifacts)
    print(f"AI Gateway de Foundry ({mode}): {artifacts.base_url}\n")
    print(describe(chat(client, settings, SHORT_PROMPT, gateway=f"foundry-ai-gateway-{mode}")))


def burst(mode: str, requests: int) -> None:
    settings = load_settings()
    artifacts = discover(settings, mode)
    client = gateway_client(artifacts)
    print(f"Ráfaga de {requests} peticiones al AI Gateway de Foundry ({mode}).\n")

    counts: dict[int, int] = {}
    for attempt in range(1, requests + 1):
        result = chat(client, settings, LONG_PROMPT, gateway=f"foundry-ai-gateway-{mode}", max_completion_tokens=600)
        counts[result.status_code] = counts.get(result.status_code, 0) + 1
        print(f"[{attempt:02d}] {describe(result, max_text=80)}")

    summary = ", ".join(f"HTTP {status}: {count}" for status, count in sorted(counts.items()))
    print(f"\nResumen: {summary}")
    print("El límite lo definiste en el portal de Foundry (Token management) y lo aplica API Management.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 3: el AI Gateway de Microsoft Foundry.")
    commands = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("inspeccionar", "Muestra lo que el AI Gateway de Foundry creó en API Management."),
        ("llamar", "Una llamada a través del AI Gateway de Foundry."),
        ("rafaga", "Ráfaga de peticiones para provocar el límite de tokens de Foundry."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--modo", choices=MODES, required=True, help="AI Gateway independiente o integrado.")
        if name == "rafaga":
            command.add_argument("--peticiones", type=int, default=20, help="Número de peticiones (por defecto 20).")

    args = parser.parse_args()
    if args.command == "inspeccionar":
        inspect(args.modo)
    elif args.command == "llamar":
        call(args.modo)
    else:
        burst(args.modo, args.peticiones)


if __name__ == "__main__":
    main()
