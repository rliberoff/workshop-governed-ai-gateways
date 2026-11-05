"""Discovery of the Foundry AI Gateway artifacts in API Management.

Enabling an AI Gateway on a Foundry account is a Foundry portal step, but its result is made of ordinary Azure
resources, as the official template that enables a project shows:
https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/project-ai-gateway

- An ARM resource link from the Foundry account to the API Management service that backs the gateway.
- A shared API in that service for the account.
- For every enabled project, a product, a subscription scoped to it, and an ARM resource link from the project
  to the product.

This module follows those links instead of hard-coding names, and builds an OpenAI-compatible client from the
operations that the shared API exposes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from azure.mgmt.apimanagement import ApiManagementClient
from openai import OpenAI

from workshop.clients import credential
from workshop.config import Settings

ARM_ENDPOINT = "https://management.azure.com"
LINKS_API_VERSION = "2016-09-01"
# Used only when a deployment-style API does not declare a default api-version query parameter.
FALLBACK_AZURE_OPENAI_API_VERSION = "2024-10-21"
DEFAULT_KEY_HEADER = "Ocp-Apim-Subscription-Key"
CHAT_COMPLETIONS_SUFFIX = "/chat/completions"

APIM_ID_PATTERN = re.compile(
    r"^/subscriptions/(?P<subscription>[^/]+)/resourceGroups/(?P<group>[^/]+)"
    r"/providers/Microsoft\.ApiManagement/service/(?P<service>[^/]+)(?:/products/(?P<product>[^/]+))?/?$",
    re.IGNORECASE,
)

MODES = ("independiente", "integrado")


@dataclass(frozen=True)
class GatewayArtifacts:
    """What the Foundry AI Gateway created for one project."""

    mode: str
    account_id: str
    project_name: str
    apim_subscription_id: str
    apim_resource_group: str
    apim_name: str
    gateway_url: str
    product_name: str
    subscription_name: str
    api_name: str
    api_path: str
    key_header: str
    operations: list[tuple[str, str]]
    base_url: str
    api_version: str | None


def _resource_links(scope_id: str) -> list[str]:
    """Return the target IDs of the ARM resource links defined at a scope."""
    token = credential().get_token(f"{ARM_ENDPOINT}/.default").token
    response = requests.get(
        f"{ARM_ENDPOINT}{scope_id}/providers/Microsoft.Resources/links",
        params={"api-version": LINKS_API_VERSION, "$filter": "atScope()"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return [item["properties"]["targetId"] for item in response.json().get("value", [])]


def _account_and_project(settings: Settings, mode: str) -> tuple[str, str]:
    if mode == "independiente":
        return settings.foundry_standalone_account_id, settings.foundry_standalone_project_name
    if mode == "integrado":
        return settings.foundry_account_id, settings.foundry_project_name
    raise ValueError(f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}.")


def _chat_operation(operations) -> tuple[str, str | None]:
    """Pick the chat completions operation, preferring an OpenAI v1 style path over a deployment-based one."""
    candidates = [
        operation
        for operation in operations
        if (operation.method or "").upper() == "POST"
        and operation.url_template.split("?")[0].rstrip("/").endswith(CHAT_COMPLETIONS_SUFFIX)
    ]
    if not candidates:
        if any(
            (operation.method or "").upper() == "POST" and operation.url_template == "/*" for operation in operations
        ):
            return "/openai/v1/chat/completions", None
        raise RuntimeError("The AI Gateway shared API exposes no POST .../chat/completions operation.")

    candidates.sort(key=lambda operation: "{" in operation.url_template.split("?")[0])
    operation = candidates[0]

    api_version = None
    for parameter in (operation.request.query_parameters if operation.request else None) or []:
        if parameter.name == "api-version":
            api_version = parameter.default_value or (parameter.values[0] if parameter.values else None)
    return operation.url_template, api_version


def discover(settings: Settings, mode: str) -> GatewayArtifacts:
    """Find the API Management artifacts that the Foundry AI Gateway created for the project of a mode."""
    account_id, project_name = _account_and_project(settings, mode)
    project_id = f"{account_id}/projects/{project_name}"

    product_links = [match for target in _resource_links(project_id) if (match := APIM_ID_PATTERN.match(target))]
    product_links = [match for match in product_links if match.group("product")]
    if not product_links:
        account_links = [target for target in _resource_links(account_id) if APIM_ID_PATTERN.match(target)]
        if account_links:
            raise RuntimeError(
                f"The account has an AI Gateway, but project '{project_name}' is not on it. "
                "Select 'Add project to gateway' in the Foundry portal."
            )
        raise RuntimeError(
            f"The account of mode '{mode}' has no AI Gateway yet. Add it in the Foundry portal (Manage > AI Gateway)."
        )

    link = product_links[0]
    group, service, product = link.group("group"), link.group("service"), link.group("product")
    management = ApiManagementClient(credential(), link.group("subscription"))

    gateway_url = management.api_management_service.get(group, service).gateway_url.rstrip("/")

    product_scope = f"/products/{product}".lower()
    subscriptions = [
        item
        for item in management.subscription.list(group, service)
        if item.scope and item.scope.lower().endswith(product_scope)
    ]
    if not subscriptions:
        raise RuntimeError(f"No API Management subscription is scoped to product '{product}'.")

    apis = list(management.product_api.list_by_product(group, service, product))
    if not apis:
        raise RuntimeError(f"Product '{product}' has no API associated yet; wait a few minutes and retry.")
    api = management.api.get(group, service, apis[0].name)

    operations = list(management.api_operation.list_by_api(group, service, api.name))
    url_template, api_version = _chat_operation(operations)

    # The OpenAI SDK appends /chat/completions, so the base URL is the operation path without that suffix.
    # A deployment-based path, such as /deployments/{deployment-id}/chat/completions, takes the deployment name.
    route = url_template.split("?")[0].rstrip("/")[: -len(CHAT_COMPLETIONS_SUFFIX)]
    deployment_based = "{" in route
    route = re.sub(r"\{[^}]+\}", settings.model, route)
    api_path = (api.path or "").strip("/")
    base_url = "/".join(part for part in (gateway_url, api_path, route.strip("/")) if part)
    if deployment_based and api_version is None:
        api_version = FALLBACK_AZURE_OPENAI_API_VERSION
    if not deployment_based:
        api_version = None

    key_header = DEFAULT_KEY_HEADER
    if api.subscription_key_parameter_names and api.subscription_key_parameter_names.header:
        key_header = api.subscription_key_parameter_names.header

    return GatewayArtifacts(
        mode=mode,
        account_id=account_id,
        project_name=project_name,
        apim_subscription_id=link.group("subscription"),
        apim_resource_group=group,
        apim_name=service,
        gateway_url=gateway_url,
        product_name=product,
        subscription_name=subscriptions[0].name,
        api_name=api.name,
        api_path=api_path,
        key_header=key_header,
        operations=[((operation.method or "").upper(), operation.url_template) for operation in operations],
        base_url=base_url,
        api_version=api_version,
    )


def gateway_client(artifacts: GatewayArtifacts) -> OpenAI:
    """OpenAI-compatible client for the project endpoint of a Foundry AI Gateway."""
    management = ApiManagementClient(credential(), artifacts.apim_subscription_id)
    key = management.subscription.list_secrets(
        artifacts.apim_resource_group, artifacts.apim_name, artifacts.subscription_name
    ).primary_key

    return OpenAI(
        base_url=f"{artifacts.base_url}/",
        api_key=key,
        default_headers={artifacts.key_header: key},
        default_query={"api-version": artifacts.api_version} if artifacts.api_version else None,
        max_retries=0,
    )


def list_service_apis(artifacts: GatewayArtifacts) -> list[tuple[str, str]]:
    """Name and path of every API in the API Management service that backs the gateway."""
    management = ApiManagementClient(credential(), artifacts.apim_subscription_id)
    return [
        (api.name, api.path or "")
        for api in management.api.list_by_service(artifacts.apim_resource_group, artifacts.apim_name)
    ]
