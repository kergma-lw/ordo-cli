import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.workflow import OperationRef, Step, StepBlock, Workflow
from ordo.runtime import execute_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RoutineExecutionTest(unittest.TestCase):
    def test_execute_runs_routine_and_returns_compact_log_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-pass.py"
            script.write_text(
                "#!/usr/bin/env python3\nprint('line 1')\nprint('line 2')\nprint('line 3')\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.pass:
                        kind: action
                        summary: Run the demo pass routine.
                        implementation:
                          argv: [".ordo/scripts/demo-pass.py"]
                        failure_modes: [routine_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine", with_={"id": "demo.pass"})),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs["routine_id"], "demo.pass")
        self.assertTrue(result.operation_results[0].outputs["log_path"].endswith(".stdout.log"))
        self.assertIn("line 3", result.operation_results[0].outputs["stdout_tail"])

    def test_execute_returns_routine_failed_for_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-fail.py"
            script.write_text(
                "#!/usr/bin/env python3\nimport sys\nprint('before fail')\nprint('boom', file=sys.stderr)\nsys.exit(3)\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.fail:
                        kind: action
                        summary: Run the demo failing routine.
                        implementation:
                          argv: [".ordo/scripts/demo-fail.py"]
                        failure_modes: [routine_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine", with_={"id": "demo.fail"})),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "execution_error")
        self.assertEqual(result.operation_results[0].status, "routine_failed")
        self.assertEqual(result.operation_results[0].outputs["exit_code"], 3)
        self.assertIn("boom", result.operation_results[0].outputs["stderr_tail"])

    def test_execute_reports_missing_registry_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine", with_={"id": "demo.pass"})),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "validation_error")
        self.assertEqual(result.diagnostics[0].code, "routine.discovery.missing")

    def test_execute_probe_data_returns_structured_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-probe.py"
            script.write_text(
                "#!/usr/bin/env python3\nimport json\nprint(json.dumps({'exists': True, 'count': 2}))\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.probe:
                        kind: probe
                        summary: Return probe data.
                        implementation:
                          argv: [".ordo/scripts/demo-probe.py"]
                        outputs:
                          mode: data
                          format: json
                        failure_modes: [probe_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine", with_={"id": "demo.probe"})),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs["data"], {"exists": True, "count": 2})

    def test_execute_probe_with_invalid_json_returns_execution_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-probe.py"
            script.write_text("#!/usr/bin/env python3\nprint('not json')\n", encoding="utf-8")
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.probe:
                        kind: probe
                        summary: Return probe data.
                        implementation:
                          argv: [".ordo/scripts/demo-probe.py"]
                        outputs:
                          mode: data
                          format: json
                        failure_modes: [probe_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine", with_={"id": "demo.probe"})),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "execution_error")
        self.assertEqual(result.operation_results[0].status, "execution_error")
        self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.routine.probe_output_invalid")


if __name__ == "__main__":
    unittest.main()
