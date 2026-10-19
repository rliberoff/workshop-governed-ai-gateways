"""OpenAI-compatible clients for the three paths of the workshop.

The same OpenAI SDK reaches the same Foundry deployment through three paths; only the base URL and the
credential change:

- Direct: Foundry OpenAI v1 endpoint with a Microsoft Entra ID token of the attendee.
- API Management: governed API with a subscription key; the gateway uses its own managed identity.
- Unity Gateway: Databricks workspace route with a Databricks token and the provider service header.
"""

from __future__ import annotations

import json
from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.mgmt.apimanagement import ApiManagementClient
from openai import OpenAI

from workshop.config import Settings

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


@lru_cache(maxsize=1)
def credential() -> DefaultAzureCredential:
    """Credential of the attendee, normally the Azure CLI sign-in."""
    return DefaultAzureCredential()


def direct_client(settings: Settings) -> OpenAI:
    """Client that calls the Foundry deployment directly, without any gateway."""
    token_provider = get_bearer_token_provider(credential(), COGNITIVE_SERVICES_SCOPE)
    # Retries are disabled in every client so the labs show each throttling response as it happens.
    return OpenAI(base_url=f"{settings.foundry_openai_v1_endpoint}/", api_key=token_provider, max_retries=0)


def apim_subscription_key(settings: Settings, product: str) -> str:
    """Read the primary key of the subscription of a product through the management API.

    Keys are never written to files or Terraform outputs; the attendee identity reads them on demand.
    """
    subscription_id = settings.apim_subscription_ids.get(product)
    if subscription_id is None:
        available = ", ".join(sorted(settings.apim_subscription_ids))
        raise ValueError(f"Unknown product '{product}'. Available products: {available}.")

    management = ApiManagementClient(credential(), settings.subscription_id)
    secrets = management.subscription.list_secrets(settings.resource_group, settings.apim_name, subscription_id)
    return secrets.primary_key


def apim_client(settings: Settings, product: str, subscription_key: str | None = None) -> OpenAI:
    """Client that calls the governed API in API Management with the key of a product subscription."""
    key = subscription_key if subscription_key is not None else apim_subscription_key(settings, product)
    # API Management reads the key from the api-key header; the policy discards it before reaching Foundry.
    return OpenAI(
        base_url=f"{settings.apim_api_base_url}/",
        api_key=key,
        default_headers={"api-key": key},
        max_retries=0,
    )


def unity_gateway_client(settings: Settings) -> OpenAI:
    """Client that calls the Foundry deployment through the Databricks Unity Gateway."""
    if settings.databricks is None:
        raise RuntimeError("The databricks layer is not provisioned. Run 'azd provision databricks' first.")

    from databricks.sdk import WorkspaceClient

    workspace = WorkspaceClient(
        host=settings.databricks.workspace_url,
        azure_workspace_resource_id=settings.databricks.workspace_resource_id,
        auth_type="azure-cli",
    )
    token = workspace.config.authenticate()["Authorization"].removeprefix("Bearer ")

    # Request tags land in the usage system table and in the inference table, to attribute consumption.
    request_tags = {"project": "governed-ai-gateways", "environment": settings.environment_name}

    return OpenAI(
        base_url=f"{settings.databricks.workspace_url}/ai-gateway/openai/v1/",
        api_key=token,
        default_headers={
            "Databricks-Model-Provider-Service": settings.databricks.model_provider_service,
            "Databricks-Ai-Gateway-Request-Tags": json.dumps(request_tags),
        },
        max_retries=0,
    )
