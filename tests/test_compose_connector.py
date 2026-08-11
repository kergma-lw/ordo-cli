import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe, execute_action
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.runtime.resolution import ResolvedOperation


class ComposeConnectorTest(unittest.TestCase):
    def test_registry_exposes_compose_family_and_operations(self) -> None:
        registry = get_public_connector_registry()

        connector = registry.get_connector("compose")

        self.assertIsNotNone(connector)
        self.assertEqual(connector.bootstrap.context_fields, ("project_directory", "compose_file", "project_name"))
        self.assertIsNotNone(registry.get_operation("compose.project"))
        self.assertIsNotNone(registry.get_operation("compose.service"))
        self.assertIsNotNone(registry.get_operation("compose.start"))
        self.assertIsNotNone(registry.get_operation("compose.stop"))
        self.assertIsNotNone(registry.get_operation("compose.remove"))

    def test_compose_bootstrap_rejects_unknown_context_fields(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"banana": 1}})
        operation = get_public_connector_registry().get_operation("compose.project")
        resolved = ResolvedOperation("compose.project", "compose", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "unknown_context_field")
        self.assertEqual(result.diagnostics[0].code, "bootstrap.compose_unknown_context_field")
        run.assert_not_called()

    def test_compose_project_probe_aggregates_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir, "project_name": "demo"}})
            operation = get_public_connector_registry().get_operation("compose.project")
            resolved = ResolvedOperation("compose.project", "compose", operation, "public")  # type: ignore[arg-type]

            ps_payload = json.dumps(
                [
                    {
                        "Project": "demo",
                        "Service": "api",
                        "State": "running",
                        "Health": "healthy",
                        "Publishers": [{"PublishedPort": 8080, "TargetPort": 8080}],
                    },
                    {
                        "Project": "demo",
                        "Service": "db",
                        "State": "exited",
                        "Health": None,
                        "Publishers": [],
                    },
                ]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\ndb\n"),
                    self._completed(stdout=ps_payload),
                ]
                result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["project"], "demo")
        self.assertEqual(result.outputs["state"], "degraded")
        self.assertEqual(result.outputs["service_counts"], {"declared": 2, "running": 1, "stopped": 1, "unhealthy": 0})
        self.assertEqual(result.outputs["services"]["api"], {"state": "running", "healthy": True})
        self.assertEqual(result.outputs["services"]["db"], {"state": "stopped", "healthy": None})
        self.assertEqual(run.call_args_list[0].kwargs.get("cwd"), temp_dir)
        self.assertEqual(run.call_args_list[1].kwargs.get("cwd"), temp_dir)
        self.assertEqual(run.call_args_list[2].kwargs.get("cwd"), temp_dir)

    def test_compose_service_probe_reports_unhealthy_running_service_as_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.service")
            resolved = ResolvedOperation(
                "compose.service",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )

            ps_payload = json.dumps(
                [
                    {
                        "Project": "demo",
                        "Service": "api",
                        "State": "running",
                        "Health": "unhealthy",
                        "Publishers": [{"PublishedPort": 8080, "TargetPort": 8080, "Protocol": "tcp"}],
                    }
                ]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=ps_payload),
                ]
                result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["state"], "degraded")
        self.assertEqual(result.outputs["healthy"], False)
        self.assertEqual(result.outputs["published_ports"], ["8080:8080/tcp"])

    def test_compose_start_is_idempotent_when_project_is_already_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.start")
            resolved = ResolvedOperation("compose.start", "compose", operation, "public", declared_with={})  # type: ignore[arg-type]

            ps_payload = json.dumps(
                [{"Project": "demo", "Service": "api", "State": "running", "Health": "healthy", "Publishers": []}]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=ps_payload),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["target_kind"], "project")
        self.assertEqual(result.outputs["state"], "running")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(len(run.call_args_list), 3)

    def test_compose_start_maps_missing_image_to_image_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.start")
            resolved = ResolvedOperation(
                "compose.start",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout="[]"),
                    self._completed(returncode=1, stderr="pull access denied for missing-image"),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "image_unavailable")
        self.assertEqual(result.diagnostics[0].code, "action.compose_start.image_unavailable")
        self.assertEqual(result.diagnostics[0].details["external_tool"], "docker")
        self.assertEqual(result.diagnostics[0].details["external_system"], "compose")

    def test_compose_stop_reports_stopped_after_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.stop")
            resolved = ResolvedOperation(
                "compose.stop",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )

            before_payload = json.dumps(
                [{"Project": "demo", "Service": "api", "State": "running", "Health": "healthy", "Publishers": []}]
            )
            after_payload = json.dumps(
                [{"Project": "demo", "Service": "api", "State": "exited", "Health": None, "Publishers": []}]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=before_payload),
                    self._completed(stdout=""),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=after_payload),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["target_kind"], "service")
        self.assertEqual(result.outputs["target"], "api")
        self.assertEqual(result.outputs["state"], "stopped")
        self.assertTrue(result.outputs["changed"])

    def test_compose_remove_is_idempotent_when_service_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.remove")
            resolved = ResolvedOperation(
                "compose.remove",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout="[]"),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["state"], "absent")
        self.assertFalse(result.outputs["changed"])

    def test_compose_remove_rejects_running_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.remove")
            resolved = ResolvedOperation(
                "compose.remove",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )
            before_payload = json.dumps(
                [{"Project": "demo", "Service": "api", "State": "running", "Health": "healthy", "Publishers": []}]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=before_payload),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "service_running")
        self.assertEqual(result.diagnostics[0].code, "action.compose_remove.service_running")

    def test_compose_remove_reports_absent_after_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"compose": {"directory": temp_dir}})
            operation = get_public_connector_registry().get_operation("compose.remove")
            resolved = ResolvedOperation(
                "compose.remove",
                "compose",
                operation,
                "public",
                declared_with={"service": "api"},
            )

            before_payload = json.dumps(
                [{"Project": "demo", "Service": "api", "State": "exited", "Health": None, "Publishers": []}]
            )

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(stdout="Docker Compose version v2.29.0\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout=before_payload),
                    self._completed(stdout="Going to remove api\n"),
                    self._completed(stdout="api\n"),
                    self._completed(stdout="[]"),
                ]
                result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["target_kind"], "service")
        self.assertEqual(result.outputs["target"], "api")
        self.assertEqual(result.outputs["state"], "absent")
        self.assertTrue(result.outputs["changed"])

    def _completed(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["command"], returncode=returncode, stdout=stdout, stderr=stderr)


if __name__ == "__main__":
    unittest.main()
