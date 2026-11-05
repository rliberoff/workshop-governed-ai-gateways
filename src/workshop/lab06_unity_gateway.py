"""Lab 6: the same Foundry deployment governed by the Databricks Unity Gateway, and every path compared."""

from __future__ import annotations

import argparse

from workshop.chat import chat, describe
from workshop.clients import apim_client, direct_client, unity_gateway_client
from workshop.config import load_settings
from workshop.foundry_gateway import MODES, discover, gateway_client
from workshop.lab02_gateway import LONG_PROMPT, SHORT_PROMPT


def call() -> None:
    settings = load_settings()
    client = unity_gateway_client(settings)
    print(f"Unity Gateway: {settings.databricks.workspace_url}/ai-gateway/openai/v1")
    print(f"Model provider service: {settings.databricks.model_provider_service}\n")
    print(describe(chat(client, settings, SHORT_PROMPT, gateway="unity-gateway")))


def burst(requests: int) -> None:
    settings = load_settings()
    client = unity_gateway_client(settings)
    print(f"Ráfaga de {requests} peticiones a través de Unity Gateway.\n")
    for attempt in range(1, requests + 1):
        result = chat(client, settings, LONG_PROMPT, gateway="unity-gateway", max_completion_tokens=600)
        print(f"[{attempt:02d}] {describe(result, max_text=80)}")
    print("\nUn 429 indica que se superó el límite de tokens por usuario del model provider service.")


def compare(product: str) -> None:
    settings = load_settings()
    paths = [
        ("Directo a Foundry", "direct", direct_client(settings)),
        (f"Azure API Management ({product})", "apim", apim_client(settings, product)),
    ]
    for mode in MODES:
        try:
            paths.append(
                (
                    f"AI Gateway de Foundry ({mode})",
                    f"foundry-ai-gateway-{mode}",
                    gateway_client(discover(settings, mode)),
                )
            )
        except RuntimeError as error:
            print(f"AI Gateway de Foundry ({mode}) omitido: {error}\n")
    if settings.databricks is not None:
        paths.append(("Databricks Unity Gateway", "unity-gateway", unity_gateway_client(settings)))
    else:
        print("La capa databricks no está desplegada: se omite Unity Gateway.\n")

    for title, gateway, client in paths:
        print(f"== {title} ==")
        print(describe(chat(client, settings, SHORT_PROMPT, gateway=gateway), max_text=160) + "\n")

    print(
        "Mismo SDK y mismo modelo: cambian la URL base, la credencial y quién aplica las políticas\n"
        "(nadie, tu API en APIM, el AI Gateway de Foundry o Unity Catalog). El modo independiente usa el\n"
        "despliegue de la segunda cuenta de Foundry; el resto, el de la cuenta principal."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 6: Databricks Unity Gateway y comparación de caminos.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("llamar", help="Una llamada a través de Unity Gateway.")

    burst_parser = commands.add_parser("rafaga", help="Ráfaga para provocar el límite de tokens por usuario.")
    burst_parser.add_argument("--peticiones", type=int, default=20, help="Número de peticiones (por defecto 20).")

    compare_parser = commands.add_parser("comparar", help="El mismo prompt por los tres caminos.")
    compare_parser.add_argument("--producto", default="premium", help="Producto de APIM (por defecto premium).")

    args = parser.parse_args()
    if args.command == "llamar":
        call()
    elif args.command == "rafaga":
        burst(args.peticiones)
    else:
        compare(args.producto)


if __name__ == "__main__":
    main()
