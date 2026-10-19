"""OpenTelemetry export to the Application Insights resource connected to the Foundry project."""

from __future__ import annotations

from azure.ai.projects import AIProjectClient
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from workshop.clients import credential
from workshop.config import Settings


def configure_tracing(settings: Settings, service_name: str) -> None:
    """Send spans to the Application Insights connected to the Foundry project, using Microsoft Entra ID.

    The connection string comes from the project connection created by Terraform, so it never lives in a file.
    Application Insights has local authentication disabled; the attendee needs Monitoring Metrics Publisher.
    """
    with AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=credential()) as project:
        connection_string = project.telemetry.get_application_insights_connection_string()

    configure_azure_monitor(
        connection_string=connection_string,
        credential=credential(),
        resource=Resource.create({SERVICE_NAME: service_name}),
    )


def flush_tracing() -> None:
    """Export buffered spans before a short-lived script exits."""
    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if callable(force_flush):
        force_flush()
