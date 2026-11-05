"""Tests for continuing a red-team scenario after an individual failure."""

import hashlib
import io
import json
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from workshop import chat, lab05_red_teaming
from workshop.chat import ChatResult


class RedTeamingTests(unittest.IsolatedAsyncioTestCase):
    def test_recovered_429_is_retained_in_status_history(self):
        responses = [ChatResult(429, "private error", 1), ChatResult(200, "answer", 1)]
        with patch.object(chat, "chat", side_effect=responses), patch.object(chat.time, "sleep"):
            result = chat.chat_with_retry(Mock(), Mock(), "private prompt", gateway="apim")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.attempt_status_codes, (429, 200))

    async def test_target_records_blocks_errors_and_recovered_throttling(self):
        errors = []
        responses = [
            ChatResult(400, '{"error":{"code":"content_filter"}}', 1, attempt_status_codes=(400,)),
            ChatResult(403, "private error", 1, attempt_status_codes=(403,)),
            ChatResult(400, '{"error":{"code":"BadRequest"}}', 1, attempt_status_codes=(400,)),
            ChatResult(200, "answer", 1, attempt_status_codes=(429, 429, 200)),
            ChatResult(429, "private error", 1, attempt_status_codes=(429,)),
        ]
        with (
            patch.object(lab05_red_teaming, "load_settings", return_value=Mock()),
            patch.object(lab05_red_teaming, "apim_client", return_value=Mock()),
            patch.object(lab05_red_teaming, "chat_with_retry", side_effect=responses),
        ):
            target, _ = lab05_red_teaming.build_target("gateway", "premium", errors)
            for index in range(len(responses)):
                messages = [{"role": "user", "content": f"private prompt {index}"}]
                if index in (2, 4):
                    with self.assertRaises(lab05_red_teaming.UnansweredAttackError):
                        await target(messages)
                else:
                    await target(messages)

        self.assertEqual([entry["status_code"] for entry in errors], [400, 403, 400, 429, 429, 429])
        self.assertEqual([entry["final_outcome"] for entry in errors],
                         ["blocked", "blocked", "unanswered", "answered", "answered", "unanswered"])
        self.assertEqual([entry["attempt"] for entry in errors], [1, 1, 1, 1, 2, 1])
        self.assertNotIn("private", json.dumps(errors))

    async def test_incomplete_objective_does_not_stop_later_strategies(self):
        first = SimpleNamespace(
            atomic_attack_name="baseline",
            run_async=AsyncMock(
                return_value=SimpleNamespace(
                    completed_results=["first result"],
                    incomplete_objectives=[("private objective", RuntimeError("private error"))],
                )
            ),
        )
        second = SimpleNamespace(
            atomic_attack_name="jailbreak",
            run_async=AsyncMock(
                return_value=SimpleNamespace(completed_results=["second result"], incomplete_objectives=[])
            ),
        )
        save_results = AsyncMock()

        failures = await lab05_red_teaming._run_atomic_attacks([first, second], 2, save_results)

        second.run_async.assert_awaited_once()
        self.assertEqual(save_results.await_count, 2)
        objective_hash = hashlib.sha256(b"private objective").hexdigest()
        self.assertEqual(failures, {"baseline": [{"objective_sha256": objective_hash}]})

    async def test_strategy_exception_does_not_stop_later_strategies(self):
        first = SimpleNamespace(
            atomic_attack_name="baseline",
            objectives=["first objective", "second objective"],
            run_async=AsyncMock(side_effect=RuntimeError("private error")),
        )
        second = SimpleNamespace(
            atomic_attack_name="jailbreak",
            run_async=AsyncMock(return_value=SimpleNamespace(completed_results=[], incomplete_objectives=[])),
        )

        failures = await lab05_red_teaming._run_atomic_attacks([first, second], 2, AsyncMock())

        second.run_async.assert_awaited_once()
        self.assertEqual(len(failures["baseline"]), 2)
        self.assertNotIn("private error", str(failures))

    def test_only_known_structured_error_codes_are_exposed(self):
        recognized = '{"error":{"code":"BadRequest","message":"private content"}}'
        unrecognized = '{"error":{"code":"private_content"}}'
        self.assertEqual(lab05_red_teaming._recognized_error_code(recognized), "BadRequest")
        for body in (unrecognized, "not json", "[]", '{"error":{"code":[]}}'):
            self.assertIsNone(lab05_red_teaming._recognized_error_code(body))

    def test_failure_detail_extracts_http_status_without_error_body(self):
        error = lab05_red_teaming.UnansweredAttackError(400, "BadRequest")
        detail = lab05_red_teaming._failure_detail("private objective", error)
        self.assertEqual(detail["status_code"], 400)
        self.assertEqual(detail["error_code"], "BadRequest")
        self.assertNotIn("private objective", str(detail))

    async def test_foundry_scenario_runs_every_strategy_and_marks_partial_failure(self):
        attacks = []
        for strategy in ("baseline", "jailbreak", "base64", "flip", "morse"):
            incomplete = []
            if strategy == "baseline":
                incomplete.append(("private objective", lab05_red_teaming.UnansweredAttackError(400)))
            attacks.append(
                SimpleNamespace(
                    atomic_attack_name=strategy,
                    run_async=AsyncMock(
                        return_value=SimpleNamespace(completed_results=[strategy], incomplete_objectives=incomplete)
                    ),
                )
            )
        failures = {}
        scenario_type = lab05_red_teaming._continuing_scenario(failures)
        scenario = scenario_type.__new__(scenario_type)
        scenario._scenario_result_id = "scenario-id"
        scenario._atomic_attacks = attacks
        scenario._max_concurrency = 2
        scenario._objective_scorer = SimpleNamespace(risk_category=SimpleNamespace(value="violence"))
        scenario._memory = Mock()
        scenario._memory.get_scenario_results.return_value = ["scenario result"]
        scenario._update_scenario_result_async = AsyncMock()

        result = await scenario.run_async()

        self.assertEqual(result, "scenario result")
        self.assertTrue(all(attack.run_async.await_count == 1 for attack in attacks))
        self.assertEqual(scenario._update_scenario_result_async.await_count, 5)
        self.assertEqual(failures["violence"]["baseline"][0]["status_code"], 400)
        scenario._memory.update_scenario_run_state.assert_called_with(
            scenario_result_id="scenario-id", scenario_run_state="FAILED"
        )

    async def test_scan_reports_incomplete_coverage_even_without_callback_errors(self):
        result = Mock()
        result.to_scorecard.return_value = {
            "risk_category_summary": [{"violence_total": 1, "hate_unfairness_total": 10}]
        }

        async def fake_scan(red_team, **kwargs):
            Path(kwargs["output_path"]).mkdir()
            return result

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(lab05_red_teaming, "Path", side_effect=lambda path: Path(directory) / path),
                patch.object(lab05_red_teaming, "load_settings", return_value=SimpleNamespace(
                    foundry_project_endpoint="https://example.org", environment_name="local"
                )),
                patch.object(lab05_red_teaming, "credential", return_value=Mock()),
                patch.object(lab05_red_teaming, "build_target", return_value=(Mock(), Counter())),
                patch.object(lab05_red_teaming.RedTeam, "__init__", return_value=None),
                patch.object(lab05_red_teaming.RedTeam, "scan", new=fake_scan),
                redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                await lab05_red_teaming.scan("gateway", "premium", 2, True)
            report = json.loads(
                (Path(directory) / "red-team-results" / "scan-gateway.json" / "incomplete-attacks.json").read_text()
            )

        self.assertEqual(error.exception.code, 1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["evaluated_per_category"]["violence"], 1)
        self.assertEqual(report["http_status_counts"], {"400": 0, "403": 0, "429": 0})

    async def test_scan_succeeds_when_all_cases_are_evaluated(self):
        result = Mock()
        result.to_scorecard.return_value = {
            "risk_category_summary": [{"violence_total": 10, "hate_unfairness_total": 10}]
        }

        async def fake_scan(red_team, **kwargs):
            Path(kwargs["output_path"]).mkdir()
            return result

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(lab05_red_teaming, "Path", side_effect=lambda path: Path(directory) / path),
                patch.object(lab05_red_teaming, "load_settings", return_value=SimpleNamespace(
                    foundry_project_endpoint="https://example.org", environment_name="local"
                )),
                patch.object(lab05_red_teaming, "credential", return_value=Mock()),
                patch.object(lab05_red_teaming, "build_target", return_value=(Mock(), Counter())),
                patch.object(lab05_red_teaming.RedTeam, "__init__", return_value=None),
                patch.object(lab05_red_teaming.RedTeam, "scan", new=fake_scan),
                redirect_stdout(io.StringIO()),
            ):
                await lab05_red_teaming.scan("gateway", "premium", 2, True)
            report = json.loads(
                (Path(directory) / "red-team-results" / "scan-gateway.json" / "incomplete-attacks.json").read_text()
            )

        self.assertTrue(report["complete"])

    async def test_scan_writes_http_errors_even_when_complete(self):
        result = Mock()
        result.to_scorecard.return_value = {
            "risk_category_summary": [{"violence_total": 10, "hate_unfairness_total": 10}]
        }
        responses = [
            ChatResult(400, '{"error":{"code":"content_filter"}}', 1),
            ChatResult(403, "private error", 1),
            ChatResult(429, "private error", 1),
            ChatResult(200, "answer", 1),
        ]

        async def fake_scan(red_team, **kwargs):
            Path(kwargs["output_path"]).mkdir()
            for index in range(3):
                await kwargs["target"]([{"role": "user", "content": f"private prompt {index}"}])
            return result

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(lab05_red_teaming, "Path", side_effect=lambda path: Path(directory) / path),
                patch.object(lab05_red_teaming, "load_settings", return_value=SimpleNamespace(
                    foundry_project_endpoint="https://example.org", environment_name="local"
                )),
                patch.object(lab05_red_teaming, "credential", return_value=Mock()),
                patch.object(lab05_red_teaming, "apim_client", return_value=Mock()),
                patch.object(lab05_red_teaming.RedTeam, "__init__", return_value=None),
                patch.object(lab05_red_teaming.RedTeam, "scan", new=fake_scan),
                patch.object(chat, "chat", side_effect=responses),
                patch.object(chat.time, "sleep"),
                redirect_stdout(io.StringIO()),
            ):
                await lab05_red_teaming.scan("gateway", "premium", 2, True)
            report = json.loads(
                (Path(directory) / "red-team-results" / "scan-gateway.json" / "incomplete-attacks.json").read_text()
            )

        self.assertTrue(report["complete"])
        self.assertEqual(report["http_status_counts"], {"400": 1, "403": 1, "429": 1})
        self.assertEqual([entry["final_outcome"] for entry in report["http_errors"]],
                         ["blocked", "blocked", "answered"])
        self.assertNotIn("private", json.dumps(report))


if __name__ == "__main__":
    unittest.main()