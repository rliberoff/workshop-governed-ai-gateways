"""Offline safety checks for standalone Foundry gateway cleanup."""

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from workshop import foundry_cleanup as cleanup


class FoundryCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.values = {
            "AZURE_ENV_NAME": "cleanup01",
            "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000001",
            "AZURE_RESOURCE_GROUP": "rg-gaig-cleanup01",
            "APIM_NAME": "apim-gaig-cleanup01",
        }
        scope = (
            f"/subscriptions/{self.values['AZURE_SUBSCRIPTION_ID']}"
            f"/resourceGroups/{self.values['AZURE_RESOURCE_GROUP']}"
        )
        self.values["FOUNDRY_STANDALONE_ACCOUNT_ID"] = (
            f"{scope}/providers/Microsoft.CognitiveServices/accounts/aif-gaig-cleanup01-sa"
        )
        self.service_id = f"{scope}/providers/Microsoft.ApiManagement/service/aigw-gaig-cleanup01"
        self.management = Mock()
        self.management.api_management_service.get.return_value = SimpleNamespace(location="Sweden Central")
        self.addCleanup(patch.stopall)
        patch.object(cleanup, "ApiManagementClient", return_value=self.management).start()
        patch.object(cleanup, "credential", return_value=Mock()).start()
        self.links = patch.object(cleanup, "_resource_links", return_value=[self.service_id + "/"]).start()
        self.group_patch = patch.object(cleanup, "_resource_group_exists", return_value=False)
        self.group_exists = self.group_patch.start()

    def manifest(self):
        return json.loads(cleanup._manifest_path(self.values, self.root).read_text(encoding="utf-8"))

    def test_prepare_records_linked_service_and_region(self):
        cleanup.prepare(self.values, self.root)
        target = self.manifest()["targets"][0]
        self.assertEqual(self.service_id, target["id"])
        self.assertEqual("swedencentral", target["location"])
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_prepare_preserves_record_after_portal_removes_link(self):
        cleanup.prepare(self.values, self.root)
        original = self.manifest()
        self.links.return_value = []
        cleanup.prepare(self.values, self.root)
        self.assertEqual(original, self.manifest())

    def test_prepare_rejects_integrated_and_foreign_targets(self):
        for target in (
            self.service_id.replace("aigw-gaig-cleanup01", self.values["APIM_NAME"]),
            self.service_id.replace("rg-gaig-cleanup01", "rg-shared"),
            self.service_id.replace(self.values["AZURE_SUBSCRIPTION_ID"], "00000000-0000-0000-0000-000000000002"),
        ):
            with self.subTest(target=target):
                self.links.return_value = [target]
                with self.assertRaises(ValueError):
                    cleanup.prepare(self.values, self.root)
        self.management.api_management_service.get.assert_not_called()

    def test_prepare_rejects_cross_environment_manifest(self):
        cleanup.prepare(self.values, self.root)
        with self.assertRaises(ValueError):
            cleanup.prepare({**self.values, "AZURE_SUBSCRIPTION_ID": "another-subscription"}, self.root)

    def test_no_link_or_account_does_not_create_manifest(self):
        self.links.return_value = []
        cleanup.prepare(self.values, self.root)
        self.assertFalse(cleanup._manifest_path(self.values, self.root).exists())
        del self.values["FOUNDRY_STANDALONE_ACCOUNT_ID"]
        cleanup.prepare(self.values, self.root)
        self.assertFalse(cleanup._manifest_path(self.values, self.root).exists())

    def test_environment_cannot_escape_local_directory(self):
        with self.assertRaises(ValueError):
            cleanup.prepare({**self.values, "AZURE_ENV_NAME": "../shared"}, self.root)

    def deleted_gateway(self):
        cleanup.prepare(self.values, self.root)
        self.management.api_management_service.get.side_effect = ResourceNotFoundError("Deleted")
        deleted = SimpleNamespace(
            service_id=self.service_id,
            deletion_date=datetime.now(UTC) + timedelta(seconds=1),
        )
        self.management.deleted_services.get_by_name.return_value = deleted
        self.management.deleted_services.begin_purge.return_value.done.return_value = True
        return deleted

    def test_purge_dry_run_does_not_change_azure_or_manifest(self):
        self.deleted_gateway()
        original = self.manifest()
        cleanup.purge(self.values, self.root)
        self.assertEqual(original, self.manifest())
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_purge_waits_for_exact_service_and_removes_manifest(self):
        self.deleted_gateway()
        cleanup.purge(self.values, self.root, execute=True)
        self.management.deleted_services.begin_purge.assert_called_once_with("aigw-gaig-cleanup01", "swedencentral")
        self.management.deleted_services.begin_purge.return_value.result.assert_called_once_with()
        self.assertFalse(cleanup._manifest_path(self.values, self.root).exists())
        cleanup.purge(self.values, self.root, execute=True)
        self.management.deleted_services.begin_purge.assert_called_once()

    def test_purge_retains_manifest_while_operation_is_running(self):
        self.deleted_gateway()
        original = self.manifest()
        poller = self.management.deleted_services.begin_purge.return_value
        poller.done.return_value = False
        poller.result.side_effect = AssertionError("Do not wait indefinitely for an unfinished purge.")
        cleanup.purge(self.values, self.root, execute=True)
        poller.wait.assert_called_once_with(timeout=60)
        poller.result.assert_not_called()
        self.assertEqual(original, self.manifest())

    def test_purge_defers_while_group_exists(self):
        self.deleted_gateway()
        self.group_exists.return_value = True
        cleanup.purge(self.values, self.root, execute=True)
        self.management.deleted_services.get_by_name.assert_not_called()
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_purge_rejects_active_service(self):
        self.deleted_gateway()
        self.management.api_management_service.get.side_effect = None
        with self.assertRaises(RuntimeError):
            cleanup.purge(self.values, self.root, execute=True)
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_purge_rejects_wrong_original_id_and_old_deletion(self):
        deleted = self.deleted_gateway()
        deleted.service_id = self.service_id.replace("rg-gaig-cleanup01", "rg-shared")
        with self.assertRaises(ValueError):
            cleanup.purge(self.values, self.root, execute=True)
        deleted.service_id = self.service_id
        deleted.deletion_date = datetime.now(UTC) - timedelta(days=1)
        with self.assertRaises(ValueError):
            cleanup.purge(self.values, self.root, execute=True)
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_purge_preserves_manifest_on_permission_error(self):
        self.deleted_gateway()
        self.management.deleted_services.begin_purge.side_effect = HttpResponseError("Forbidden")
        with self.assertRaises(HttpResponseError):
            cleanup.purge(self.values, self.root, execute=True)
        self.assertTrue(cleanup._manifest_path(self.values, self.root).exists())

    def test_purge_preserves_manifest_when_polling_fails(self):
        self.deleted_gateway()
        original = self.manifest()
        poller = self.management.deleted_services.begin_purge.return_value
        poller.wait.side_effect = HttpResponseError("Polling failed")
        with self.assertRaises(HttpResponseError):
            cleanup.purge(self.values, self.root, execute=True)
        poller.result.assert_not_called()
        self.assertEqual(original, self.manifest())

    def test_purge_retains_pending_record_until_soft_delete_is_visible(self):
        self.deleted_gateway()
        self.management.deleted_services.get_by_name.side_effect = ResourceNotFoundError("Not visible yet")
        cleanup.purge(self.values, self.root, execute=True)
        self.assertTrue(cleanup._manifest_path(self.values, self.root).exists())
        self.management.deleted_services.begin_purge.assert_not_called()

    def test_postdown_works_after_terraform_outputs_are_removed(self):
        self.deleted_gateway()
        remaining_values = {
            key: self.values[key] for key in ("AZURE_ENV_NAME", "AZURE_SUBSCRIPTION_ID")
        }
        with (
            patch.dict(cleanup.os.environ, remaining_values, clear=True),
            patch("sys.argv", ["foundry_cleanup", "purge", "--execute"]),
            patch.object(cleanup.Path, "cwd", return_value=self.root),
            patch.object(cleanup, "_read_azd_values") as read_values,
        ):
            cleanup.main()
        read_values.assert_not_called()
        self.management.deleted_services.begin_purge.assert_called_once_with("aigw-gaig-cleanup01", "swedencentral")

    def test_group_lookup_only_accepts_not_found_as_deleted(self):
        cleanup.prepare(self.values, self.root)
        self.group_patch.stop()
        response = Mock(status_code=403)
        response.raise_for_status.side_effect = HttpResponseError("Forbidden")
        with patch.object(cleanup.requests, "get", return_value=response):
            with self.assertRaises(HttpResponseError):
                cleanup.purge(self.values, self.root, execute=True)
            response.status_code = 404
            self.assertFalse(cleanup._resource_group_exists(self.manifest()))
            response.status_code = 200
            response.raise_for_status.side_effect = None
            self.assertTrue(cleanup._resource_group_exists(self.manifest()))
        self.management.deleted_services.begin_purge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
