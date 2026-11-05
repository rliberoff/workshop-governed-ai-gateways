"""OpenTelemetry export to the Application Insights resource connected to the Foundry project."""

from __future__ import annotations

import requests
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from workshop.clients import credential
from workshop.config import Settings


def _application_insights_connection_string(settings: Settings) -> str:
    token = credential().get_token("https://management.azure.com/.default")
    headers = {"Authorization": f"Bearer {token.token}"}
    project_id = f"{settings.foundry_account_id}/projects/{settings.foundry_project_name}"
    response = requests.get(
        f"https://management.azure.com{project_id}/connections",
        params={"api-version": "2025-06-01"},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    target = next(
        (
            connection["properties"]["target"]
            for connection in response.json().get("value", [])
            if connection.get("properties", {}).get("category") == "AppInsights"
        ),
        None,
    )
    if not target:
        raise RuntimeError("The Foundry project has no Application Insights connection.")

    response = requests.get(
        f"https://management.azure.com{target}",
        params={"api-version": "2020-02-02"},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    connection_string = response.json().get("properties", {}).get("ConnectionString")
    if not connection_string:
        raise RuntimeError("The connected Application Insights resource has no connection string.")
    return connection_string


def configure_tracing(settings: Settings, service_name: str) -> None:
    """Send spans to the Application Insights connected to the Foundry project, using Microsoft Entra ID.

    The connection string is read through ARM from the resource linked by Terraform and never saved to a file.
    Application Insights has local authentication disabled; the attendee needs Monitoring Metrics Publisher.
    """
    configure_azure_monitor(
        connection_string=_application_insights_connection_string(settings),
        credential=credential(),
        resource=Resource.create({SERVICE_NAME: service_name}),
    )


def flush_tracing() -> None:
    """Export buffered spans before a short-lived script exits."""
    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if callable(force_flush):
        force_flush()
