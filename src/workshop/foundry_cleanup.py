"""Record and purge only the standalone Foundry gateway of an isolated workshop environment."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.apimanagement import ApiManagementClient

from workshop.clients import credential
from workshop.config import _read_azd_values, _require
from workshop.foundry_gateway import APIM_ID_PATTERN, ARM_ENDPOINT, _resource_links

MANIFEST_NAME = "foundry-cleanup.json"
PURGE_WAIT_SECONDS = 60


def _manifest_path(values: dict[str, str], root: Path) -> Path:
    environment = _require(values, "AZURE_ENV_NAME")
    if not re.fullmatch(r"[a-z0-9]{2,10}", environment):
        raise ValueError("Cleanup requires a workshop environment ID of 2-10 lowercase letters or digits.")
    return root / ".azure" / environment / MANIFEST_NAME


def _validate(manifest: dict, values: dict[str, str]) -> None:
    expected = {
        "environment": _require(values, "AZURE_ENV_NAME"),
        "subscription": _require(values, "AZURE_SUBSCRIPTION_ID"),
        "group": values.get("AZURE_RESOURCE_GROUP") or manifest["group"],
    }
    for key, value in expected.items():
        if manifest[key].casefold() != value.casefold():
            raise ValueError(f"Cleanup manifest {key} does not match the selected environment.")
    if values.get("APIM_NAME") and manifest["terraform_apim"].casefold() != values["APIM_NAME"].casefold():
        raise ValueError("Cleanup manifest does not match the Terraform API Management instance.")
    for target in manifest["targets"]:
        match = APIM_ID_PATTERN.fullmatch(target["id"])
        if (
            not match
            or match.group("product")
            or match.group("subscription").casefold() != expected["subscription"].casefold()
            or match.group("group").casefold() != expected["group"].casefold()
            or match.group("service").casefold() == manifest["terraform_apim"].casefold()
        ):
            raise ValueError("Refusing cleanup outside the isolated standalone gateway scope.")


def prepare(values: dict[str, str], root: Path) -> None:
    """Remember the linked service before the portal or Terraform removes its discovery links."""
    path = _manifest_path(values, root)
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if manifest is not None:
        _validate(manifest, values)
    account_id = values.get("FOUNDRY_STANDALONE_ACCOUNT_ID")
    if not account_id:
        print("No standalone Foundry account output; keeping any pending cleanup manifest.")
        return

    if manifest is None:
        manifest = {
            "environment": _require(values, "AZURE_ENV_NAME"),
            "subscription": _require(values, "AZURE_SUBSCRIPTION_ID"),
            "group": _require(values, "AZURE_RESOURCE_GROUP"),
            "terraform_apim": _require(values, "APIM_NAME"),
            "targets": [],
        }
    _validate(manifest, values)
    expected_scope = (
        f"/subscriptions/{manifest['subscription']}/resourceGroups/{manifest['group']}"
        "/providers/Microsoft.CognitiveServices/accounts/"
    )
    if (
        not account_id.casefold().startswith(expected_scope.casefold())
        or "/" in account_id[len(expected_scope) :]
        or account_id.casefold() == values.get("FOUNDRY_ACCOUNT_ID", "").casefold()
    ):
        raise ValueError("Standalone Foundry account does not belong to the isolated environment.")
    try:
        links = _resource_links(account_id)
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 404:
            raise
        links = []

    management = ApiManagementClient(credential(), manifest["subscription"])
    for target_id in links:
        match = APIM_ID_PATTERN.fullmatch(target_id)
        if not match or match.group("product"):
            continue
        target = {"id": target_id.rstrip("/")}
        candidate = {**manifest, "targets": [target]}
        _validate(candidate, values)
        service = management.api_management_service.get(match.group("group"), match.group("service"))
        target["location"] = service.location.lower().replace(" ", "")
        target["captured_at"] = datetime.now(UTC).isoformat()
        manifest["targets"] = [
            item for item in manifest["targets"] if item["id"].casefold() != target["id"].casefold()
        ] + [target]

    if not manifest["targets"]:
        print("No standalone gateway link found; no service will be purged.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(manifest['targets'])} standalone gateway(s) in {path}.")


def _resource_group_exists(manifest: dict) -> bool:
    response = requests.get(
        f"{ARM_ENDPOINT}/subscriptions/{manifest['subscription']}/resourceGroups/{manifest['group']}",
        params={"api-version": "2021-04-01"},
        headers={"Authorization": f"Bearer {credential().get_token(f'{ARM_ENDPOINT}/.default').token}"},
        timeout=30,
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def purge(values: dict[str, str], root: Path, *, execute: bool = False) -> None:
    """Purge recorded, soft-deleted services only after their isolated resource group is gone."""
    path = _manifest_path(values, root)
    if not path.exists():
        print("No standalone gateway cleanup manifest; nothing to purge.")
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _validate(manifest, values)
    print("Checking whether standalone gateway cleanup is eligible.", flush=True)
    if _resource_group_exists(manifest):
        print("Workshop resource group still exists; standalone gateway cleanup is deferred.")
        return

    management = ApiManagementClient(credential(), manifest["subscription"])
    for target in list(manifest["targets"]):
        match = APIM_ID_PATTERN.fullmatch(target["id"])
        group, service = match.group("group"), match.group("service")
        print(f"Checking active and soft-deleted records for standalone gateway '{service}'.", flush=True)
        try:
            management.api_management_service.get(group, service)
        except ResourceNotFoundError:
            pass
        else:
            raise RuntimeError(f"Refusing to purge active API Management service '{service}'.")
        try:
            deleted = management.deleted_services.get_by_name(service, target["location"])
        except ResourceNotFoundError:
            print(f"No soft-deleted record for '{service}'; retaining the manifest for a later retry.")
            continue
        if (
            not deleted.service_id
            or deleted.service_id.rstrip("/").casefold() != target["id"].casefold()
            or deleted.deletion_date is None
            or deleted.deletion_date < datetime.fromisoformat(target["captured_at"])
        ):
            raise ValueError(
                f"Refusing to purge '{service}': deleted-service identity or deletion date does not match."
            )
        if not execute:
            print(f"Would permanently purge standalone gateway '{service}' in {target['location']}.")
            continue
        print(f"Requesting permanent purge of standalone gateway '{service}'.", flush=True)
        poller = management.deleted_services.begin_purge(service, target["location"])
        print(f"Waiting up to {PURGE_WAIT_SECONDS} seconds for the purge of '{service}'.", flush=True)
        poller.wait(timeout=PURGE_WAIT_SECONDS)
        if not poller.done():
            print(
                f"Purge of '{service}' is still running in Azure; retaining the manifest for a later retry.",
                flush=True,
            )
            continue
        poller.result()
        manifest["targets"].remove(target)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Permanently purged standalone gateway '{service}'.")

    if execute and not manifest["targets"]:
        path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scoped cleanup of the standalone Foundry gateway.")
    parser.add_argument("command", choices=("prepare", "purge"))
    parser.add_argument(
        "--execute", action="store_true", help="Permanently purge recorded gateways; default is dry-run."
    )
    args = parser.parse_args()
    values = dict(os.environ) if os.environ.get("AZURE_ENV_NAME") else _read_azd_values()
    if args.command == "prepare":
        prepare(values, Path.cwd())
    else:
        purge(values, Path.cwd(), execute=args.execute)


if __name__ == "__main__":
    main()
