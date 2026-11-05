"""Lab 1: direct consumption of the Foundry model deployment, the starting point before any gateway."""

from __future__ import annotations

import argparse

from workshop.chat import chat, describe
from workshop.clients import direct_client
from workshop.config import load_settings

PROMPT = "Explica en dos frases qué es un AI gateway y por qué importa en una empresa."


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 1: consumo directo del modelo en Microsoft Foundry.")
    parser.add_argument("--repeticiones", type=int, default=3, help="Número de llamadas consecutivas (por defecto 3).")
    args = parser.parse_args()

    settings = load_settings()
    client = direct_client(settings)

    print(f"Endpoint directo: {settings.foundry_openai_v1_endpoint}")
    print(f"Modelo: {settings.model}\n")

    total_tokens = 0
    for attempt in range(1, args.repeticiones + 1):
        result = chat(client, settings, PROMPT, gateway="direct")
        total_tokens += (result.input_tokens or 0) + (result.output_tokens or 0)
        print(f"[{attempt}] {describe(result)}\n")

    print(f"Tokens consumidos en total: {total_tokens}")
    print(
        "Observa lo que NO hay: ninguna cuota por consumidor, ningún punto central de políticas y ninguna\n"
        "cabecera que indique el presupuesto restante. Cualquier identidad con el rol Foundry User puede\n"
        "consumir hasta agotar la cuota del despliegue."
    )


if __name__ == "__main__":
    main()
