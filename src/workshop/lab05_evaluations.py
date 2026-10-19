"""Lab 5b: quality and safety evaluations in Microsoft Foundry of the answers served through the gateway."""

from __future__ import annotations

import argparse
import json
import time
from importlib import resources

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import TestingCriterionAzureAIEvaluator
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_jsonl_run_data_source_param import (
    CreateEvalJSONLRunDataSourceParam,
    SourceFileContent,
    SourceFileContentContent,
)

from workshop.chat import chat
from workshop.clients import apim_client, credential
from workshop.config import Settings, load_settings
from workshop.lab05_red_teaming import SYSTEM_PROMPT


def load_dataset() -> list[dict[str, str]]:
    content = resources.files("workshop.data").joinpath("evaluation.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def generate_answers(settings: Settings, product: str) -> list[dict[str, str]]:
    """Answer every query through the governed path, as the production application would."""
    client = apim_client(settings, product)
    items = []
    for row in load_dataset():
        result = chat(client, settings, row["query"], gateway="apim", system=SYSTEM_PROMPT)
        response = result.text if result.ok else f"Error HTTP {result.status_code}"
        print(f"- {row['query']} -> HTTP {result.status_code}")
        items.append({"query": row["query"], "response": response, "ground_truth": row["ground_truth"]})
    return items


def testing_criteria(model: str) -> list[TestingCriterionAzureAIEvaluator]:
    """Built-in evaluators: two AI-assisted quality metrics, one safety metric and one lexical metric."""
    return [
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="coherence",
            evaluator_name="builtin.coherence",
            initialization_parameters={"model": model},
            data_mapping={"query": "{{item.query}}", "response": "{{item.response}}"},
        ),
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="fluency",
            evaluator_name="builtin.fluency",
            initialization_parameters={"model": model},
            data_mapping={"response": "{{item.response}}"},
        ),
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="violence",
            evaluator_name="builtin.violence",
            initialization_parameters={"model": model},
            data_mapping={"query": "{{item.query}}", "response": "{{item.response}}"},
        ),
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name="f1",
            evaluator_name="builtin.f1_score",
            data_mapping={"response": "{{item.response}}", "ground_truth": "{{item.ground_truth}}"},
        ),
    ]


def evaluate(product: str) -> None:
    settings = load_settings()
    print("Generando respuestas a través del gateway:\n")
    items = generate_answers(settings, product)

    with (
        AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=credential()) as project,
        project.get_openai_client() as client,
    ):
        evaluation = client.evals.create(
            name=f"taller-{settings.environment_name}-calidad",
            data_source_config=DataSourceConfigCustom(
                type="custom",
                item_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "response": {"type": "string"},
                        "ground_truth": {"type": "string"},
                    },
                    "required": ["query", "response", "ground_truth"],
                },
                include_sample_schema=True,
            ),
            testing_criteria=testing_criteria(settings.model),
        )

        run = client.evals.runs.create(
            eval_id=evaluation.id,
            name="respuestas-gateway",
            data_source=CreateEvalJSONLRunDataSourceParam(
                type="jsonl",
                source=SourceFileContent(
                    type="file_content",
                    content=[SourceFileContentContent(item=item) for item in items],
                ),
            ),
        )

        print("\nEvaluación en curso en Microsoft Foundry", end="", flush=True)
        while run.status not in ("completed", "failed", "canceled"):
            time.sleep(5)
            print(".", end="", flush=True)
            run = client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        print(f" {run.status}\n")

        for criterion in run.per_testing_criteria_results or []:
            total = criterion.passed + criterion.failed
            print(f"{criterion.testing_criteria}: {criterion.passed}/{total} superadas")
        print(f"\nInforme en el portal de Foundry: {run.report_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 5b: evaluaciones de calidad y seguridad en Foundry.")
    parser.add_argument("--producto", default="premium", help="Producto de APIM (por defecto premium).")
    args = parser.parse_args()
    evaluate(args.producto)


if __name__ == "__main__":
    main()
