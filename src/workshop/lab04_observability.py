"""Lab 4: traceability and observability of the governed calls."""

from __future__ import annotations

import argparse
from datetime import timedelta
from importlib import resources

from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from opentelemetry import trace

from workshop.chat import chat, describe
from workshop.clients import apim_client, credential
from workshop.config import load_settings
from workshop.telemetry import configure_tracing, flush_tracing

QUESTIONS = (
    "¿Qué diferencia hay entre una cuota de tokens por minuto y una cuota diaria?",
    "Da un ejemplo de por qué conviene registrar el uso de tokens por equipo.",
    "¿Qué es la propagación de contexto W3C en una traza distribuida?",
)

QUERIES = {
    "tokens": "tokens-by-subscription.kql",
    "estados": "responses-by-status.kql",
}


def traces(product: str) -> None:
    settings = load_settings()
    configure_tracing(settings, service_name="workshop-lab04")
    client = apim_client(settings, product)
    tracer = trace.get_tracer("workshop.lab04")

    # A parent span groups the three calls of one conversation, as a real application would do.
    with tracer.start_as_current_span("lab04.conversation") as conversation:
        trace_id = f"{conversation.get_span_context().trace_id:032x}"
        for question in QUESTIONS:
            print(describe(chat(client, settings, question, gateway="apim"), max_text=120) + "\n")

    flush_tracing()
    print(f"Trace ID (OperationId en Application Insights): {trace_id}")
    print("Espera 2-5 minutos a la ingesta y ejecuta:")
    print(f"  uv run python -m workshop.lab04_observability traza --id {trace_id}")


def _print_table(title: str, query: str) -> None:
    settings = load_settings()
    client = LogsQueryClient(credential())
    response = client.query_workspace(settings.log_analytics_workspace_id, query, timespan=timedelta(hours=1))

    print(f"== {title} ==")
    if response.status == LogsQueryStatus.FAILURE:
        print(f"La consulta falló: {response}")
        return

    tables = response.tables if response.status == LogsQueryStatus.SUCCESS else response.partial_data
    for table in tables:
        if not table.rows:
            print("(sin filas todavía: la ingesta tarda unos minutos)")
            continue
        print(" | ".join(table.columns))
        for row in table.rows:
            print(" | ".join(_shorten(value) for value in row))
    print()


def _shorten(value: object, limit: int = 120) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _query(file_name: str) -> str:
    return resources.files("workshop.queries").joinpath(file_name).read_text(encoding="utf-8")


def queries(names: list[str]) -> None:
    for name in names:
        _print_table(name, _query(QUERIES[name]))


def trace_by_id(trace_id: str) -> None:
    _print_table(f"traza {trace_id}", _query("end-to-end-trace.kql").replace("{trace_id}", trace_id))


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratorio 4: trazabilidad y observabilidad.")
    commands = parser.add_subparsers(dest="command", required=True)

    traces_parser = commands.add_parser("generar", help="Genera una conversación trazada con OpenTelemetry.")
    traces_parser.add_argument("--producto", default="premium", help="Producto de APIM (por defecto premium).")

    queries_parser = commands.add_parser("consultas", help="Ejecuta consultas KQL sobre los registros del gateway.")
    queries_parser.add_argument(
        "--consulta", choices=sorted(QUERIES), nargs="+", default=sorted(QUERIES), help="Consultas a ejecutar."
    )

    trace_parser = commands.add_parser("traza", help="Muestra todos los spans de una traza distribuida.")
    trace_parser.add_argument("--id", required=True, help="Trace ID impreso por el comando generar.")

    args = parser.parse_args()
    if args.command == "generar":
        traces(args.producto)
    elif args.command == "consultas":
        queries(args.consulta)
    else:
        trace_by_id(args.id)


if __name__ == "__main__":
    main()
