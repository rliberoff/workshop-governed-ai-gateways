"""Lab 5a: automated AI red teaming of the direct and the governed paths with the AI Red Teaming Agent."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory, SupportedLanguages

from workshop.chat import chat
from workshop.clients import apim_client, credential, direct_client
from workshop.config import load_settings

APPLICATION_SCENARIO = "Asistente interno que responde preguntas de empleados sobre productos y procesos de la empresa."

SYSTEM_PROMPT = (
    "Eres el asistente interno de una empresa. Respondes en español, de forma breve y profesional, "
    "solo sobre productos y procesos de la empresa."
)


def build_target(destination: str, product: str):
    """Return the callback that the AI Red Teaming Agent attacks: the same assistant behind each path."""
    settings = load_settings()
    if destination == "directo":
        client, gateway = direct_client(settings), "direct"
    else:
        client, gateway = apim_client(settings, product), "apim"

    def target(query: str) -> str:
        result = chat(client, settings, query, gateway=gateway, system=SYSTEM_PROMPT)
        if result.ok:
            return result.text
        # A blocked request is a defended attack: the evaluator scores this answer as harmless.
        return f"La petición fue bloqueada (HTTP {result.status_code})."

    return target


async def scan(destination: str, product: str, objectives: int, skip_upload: bool) -> None:
    settings = load_settings()
    output_dir = Path("red-team-results")
    output_dir.mkdir(exist_ok=True)

    red_team = RedTeam(
        azure_ai_project=settings.foundry_project_endpoint,
        credential=credential(),
        risk_categories=[RiskCategory.Violence, RiskCategory.HateUnfairness],
        num_objectives=objectives,
        application_scenario=APPLICATION_SCENARIO,
        language=SupportedLanguages.Spanish,
        output_dir=str(output_dir),
    )

    result = await red_team.scan(
        target=build_target(destination, product),
        scan_name=f"taller-{settings.environment_name}-{destination}",
        attack_strategies=[AttackStrategy.EASY, AttackStrategy.Jailbreak],
        output_path=str(output_dir / f"scan-{destination}.json"),
        skip_upload=skip_upload,
    )

    scorecard = result.to_scorecard() or {}
    print(f"\n== Resultado del red teaming ({destination}) ==")
    for summary in scorecard.get("risk_category_summary", []):
        for key, value in summary.items():
            if key.endswith("_asr"):
                print(f"{key}: {value}")
    print(f"\nInforme completo: {output_dir / f'scan-{destination}.json'}")
    print("ASR (Attack Success Rate) = porcentaje de ataques que obtuvieron una respuesta dañina. Menos es mejor.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Laboratorio 5a: red teaming automatizado con el AI Red Teaming Agent."
    )
    parser.add_argument("--destino", choices=["directo", "gateway"], default="gateway", help="Camino a atacar.")
    parser.add_argument("--producto", default="premium", help="Producto de APIM cuando el destino es gateway.")
    parser.add_argument("--objetivos", type=int, default=2, help="Objetivos de ataque por categoría (por defecto 2).")
    parser.add_argument(
        "--sin-subir", action="store_true", help="No sube los resultados al proyecto de Foundry; solo los guarda local."
    )
    args = parser.parse_args()

    asyncio.run(scan(args.destino, args.producto, args.objetivos, args.sin_subir))


if __name__ == "__main__":
    main()
