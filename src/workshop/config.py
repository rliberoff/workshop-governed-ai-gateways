"""Workshop settings read from the selected azd environment.

The azd environment is the single source of configuration: Terraform outputs land there after each
`azd provision`, so the lab scripts never need a hand-written .env file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class DatabricksSettings:
    """Values written by the optional databricks layer."""

    workspace_url: str
    workspace_resource_id: str
    model_provider_service: str
    schema: str


@dataclass(frozen=True)
class Settings:
    """Values written by the resources layer."""

    environment_name: str
    subscription_id: str
    resource_group: str
    foundry_account_id: str
    foundry_project_name: str
    foundry_standalone_account_id: str
    foundry_standalone_project_name: str
    foundry_openai_v1_endpoint: str
    foundry_project_endpoint: str
    model: str
    apim_name: str
    apim_api_base_url: str
    apim_subscription_ids: dict[str, str]
    log_analytics_workspace_id: str
    reasoning_effort: str | None
    databricks: DatabricksSettings | None


def _read_azd_values() -> dict[str, str]:
    azd = shutil.which("azd")
    if azd is None:
        raise RuntimeError("Azure Developer CLI (azd) was not found in PATH.")

    result = subprocess.run(
        [azd, "env", "get-values", "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"'azd env get-values' failed: {result.stderr.strip()}")

    return json.loads(result.stdout)


def _require(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise RuntimeError(f"The azd environment has no value for {key}. Run 'azd provision resources' and try again.")
    return value


def _databricks(values: dict[str, str]) -> DatabricksSettings | None:
    keys = (
        "DATABRICKS_WORKSPACE_URL",
        "DATABRICKS_WORKSPACE_RESOURCE_ID",
        "DATABRICKS_MODEL_PROVIDER_SERVICE",
        "DATABRICKS_SCHEMA",
    )
    if not all(values.get(key, "").strip() for key in keys):
        return None

    return DatabricksSettings(
        workspace_url=values["DATABRICKS_WORKSPACE_URL"].rstrip("/"),
        workspace_resource_id=values["DATABRICKS_WORKSPACE_RESOURCE_ID"],
        model_provider_service=values["DATABRICKS_MODEL_PROVIDER_SERVICE"],
        schema=values["DATABRICKS_SCHEMA"],
    )


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and validate the settings of the selected azd environment."""
    values = _read_azd_values()

    # gpt-6-luna is a reasoning model; a low effort keeps latency and token usage small in the labs.
    # Set MODEL_REASONING_EFFORT to an empty string when the deployed model does not support reasoning.
    reasoning_effort = values.get("MODEL_REASONING_EFFORT", "low").strip() or None

    return Settings(
        environment_name=_require(values, "AZURE_ENV_NAME"),
        subscription_id=_require(values, "AZURE_SUBSCRIPTION_ID"),
        resource_group=_require(values, "AZURE_RESOURCE_GROUP"),
        foundry_account_id=_require(values, "FOUNDRY_ACCOUNT_ID"),
        foundry_project_name=_require(values, "FOUNDRY_PROJECT_NAME"),
        foundry_standalone_account_id=_require(values, "FOUNDRY_STANDALONE_ACCOUNT_ID"),
        foundry_standalone_project_name=_require(values, "FOUNDRY_STANDALONE_PROJECT_NAME"),
        foundry_openai_v1_endpoint=_require(values, "FOUNDRY_OPENAI_V1_ENDPOINT").rstrip("/"),
        foundry_project_endpoint=_require(values, "FOUNDRY_PROJECT_ENDPOINT"),
        model=_require(values, "FOUNDRY_MODEL_DEPLOYMENT_NAME"),
        apim_name=_require(values, "APIM_NAME"),
        apim_api_base_url=_require(values, "APIM_API_BASE_URL").rstrip("/"),
        apim_subscription_ids=json.loads(_require(values, "APIM_SUBSCRIPTION_IDS")),
        log_analytics_workspace_id=_require(values, "LOG_ANALYTICS_WORKSPACE_ID"),
        reasoning_effort=reasoning_effort,
        databricks=_databricks(values),
    )
