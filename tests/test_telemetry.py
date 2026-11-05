"""Offline checks for authenticated tracing configuration through ARM."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from requests import HTTPError

from workshop import telemetry


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        scope = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-gaig-tracing01"
        self.settings = SimpleNamespace(
            foundry_account_id=f"{scope}/providers/Microsoft.CognitiveServices/accounts/aif-gaig-tracing01",
            foundry_project_name="proj-gaig-tracing01",
        )
        self.target = f"{scope}/providers/Microsoft.Insights/components/appi-gaig-tracing01"
        self.connection_string = (
            "InstrumentationKey=00000000-0000-0000-0000-000000000001;"
            "IngestionEndpoint=https://swedencentral-0.in.applicationinsights.azure.com/"
        )
        self.connections = Mock()
        self.connections.json.return_value = {
            "value": [
                {"properties": {"category": "AppConfig", "target": "https://configuration.azconfig.io"}},
                {"properties": {"category": "AppInsights", "target": self.target}},
            ]
        }
        self.component = Mock()
        self.component.json.return_value = {"properties": {"ConnectionString": self.connection_string}}
        self.addCleanup(patch.stopall)
        self.identity = patch.object(telemetry, "credential").start().return_value
        self.identity.get_token.return_value.token = "token-for-unit-tests"
        self.get = patch.object(telemetry.requests, "get", side_effect=[self.connections, self.component]).start()
        self.configure = patch.object(telemetry, "configure_azure_monitor").start()

    def test_reads_linked_component_and_configures_authenticated_export(self):
        telemetry.configure_tracing(self.settings, service_name="workshop-lab04")

        self.identity.get_token.assert_called_once_with("https://management.azure.com/.default")
        headers = {"Authorization": "Bearer token-for-unit-tests"}
        self.assertEqual(
            [
                call(
                    f"https://management.azure.com{self.settings.foundry_account_id}"
                    f"/projects/{self.settings.foundry_project_name}/connections",
                    params={"api-version": "2025-06-01"},
                    headers=headers,
                    timeout=30,
                ),
                call(
                    f"https://management.azure.com{self.target}",
                    params={"api-version": "2020-02-02"},
                    headers=headers,
                    timeout=30,
                ),
            ],
            self.get.call_args_list,
        )
        self.connections.raise_for_status.assert_called_once_with()
        self.component.raise_for_status.assert_called_once_with()
        self.configure.assert_called_once()
        arguments = self.configure.call_args.kwargs
        self.assertEqual(self.connection_string, arguments["connection_string"])
        self.assertIs(self.identity, arguments["credential"])
        self.assertEqual("workshop-lab04", arguments["resource"].attributes["service.name"])

    def test_missing_project_connection_does_not_configure_export(self):
        self.connections.json.return_value = {"value": []}

        with self.assertRaisesRegex(RuntimeError, "no Application Insights connection"):
            telemetry.configure_tracing(self.settings, service_name="workshop-lab04")

        self.assertEqual(1, self.get.call_count)
        self.configure.assert_not_called()

    def test_missing_connection_string_does_not_configure_export(self):
        self.component.json.return_value = {"properties": {}}

        with self.assertRaisesRegex(RuntimeError, "no connection string"):
            telemetry.configure_tracing(self.settings, service_name="workshop-lab04")

        self.configure.assert_not_called()

    def test_project_read_error_stops_before_reading_component(self):
        self.connections.raise_for_status.side_effect = HTTPError("Project read forbidden")

        with self.assertRaises(HTTPError):
            telemetry.configure_tracing(self.settings, service_name="workshop-lab04")

        self.assertEqual(1, self.get.call_count)
        self.configure.assert_not_called()

    def test_component_read_error_does_not_configure_export(self):
        self.component.raise_for_status.side_effect = HTTPError("Component not found")

        with self.assertRaises(HTTPError):
            telemetry.configure_tracing(self.settings, service_name="workshop-lab04")

        self.configure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
