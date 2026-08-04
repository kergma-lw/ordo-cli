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
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine.demo.pass")),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs["routine_id"], "demo.pass")
        self.assertTrue(result.operation_results[0].outputs["log_path"].endswith(".stdout.log"))
        self.assertTrue(result.operation_results[0].outputs["stdout_log_path"].endswith(".stdout.log"))
        self.assertTrue(result.operation_results[0].outputs["stderr_log_path"].endswith(".stderr.log"))
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
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine.demo.fail")),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "execution_error")
        self.assertEqual(result.operation_results[0].status, "routine_failed")
        self.assertEqual(result.operation_results[0].outputs["exit_code"], 3)
        self.assertTrue(result.operation_results[0].outputs["stdout_log_path"].endswith(".stdout.log"))
        self.assertTrue(result.operation_results[0].outputs["stderr_log_path"].endswith(".stderr.log"))
        self.assertIn("boom", result.operation_results[0].outputs["stderr_tail"])

    def test_execute_reports_missing_registry_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine.demo.pass")),)),),
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
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine.demo.probe")),)),),
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
                blocks=(StepBlock(steps=(Step(name="run-routine", operation=OperationRef("routine.demo.probe")),)),),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "execution_error")
        self.assertEqual(result.operation_results[0].status, "execution_error")
        self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.routine.probe_output_invalid")

    def test_execute_passes_selected_scalar_references_to_routine_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-env.py"
            script.write_text(
                "#!/usr/bin/env python3\nimport json\nimport os\nprint(json.dumps({'profile': os.environ.get('ORDO_INPUTS_PROFILE'), 'mode': os.environ.get('ORDO_INPUTS_REVIEW_MODE'), 'path': os.environ.get('ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH')}))\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.env:
                        kind: probe
                        summary: Return selected routine environment values.
                        implementation:
                          argv: [".ordo/scripts/demo-env.py"]
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
                inputs={"profile": "review", "review_mode": "strict"},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="collect", value={"path": "/tmp/demo.txt"}, register="collect"),
                            Step(
                                name="run-routine",
                                operation=OperationRef(
                                    "routine.demo.env",
                                    with_={"env": ["inputs.profile", "inputs.review_mode", "step.collect.outputs.value.path"]},
                                ),
                            ),
                        ),
                    ),
                ),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(
            result.operation_results[1].outputs["data"],
            {"profile": "review", "mode": "strict", "path": "/tmp/demo.txt"},
        )

    def test_execute_rejects_non_scalar_env_reference_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "scripts").mkdir(parents=True)
            script = root / ".ordo" / "scripts" / "demo-env.py"
            script.write_text("#!/usr/bin/env python3\nprint('unreachable')\n", encoding="utf-8")
            script.chmod(0o755)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.env:
                        kind: action
                        summary: Consume routine environment values.
                        implementation:
                          argv: [".ordo/scripts/demo-env.py"]
                        failure_modes: [routine_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="demo",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="collect", value={"path": "/tmp/demo.txt"}, register="collect"),
                            Step(
                                name="run-routine",
                                operation=OperationRef("routine.demo.env", with_={"env": ["step.collect.outputs.value"]}),
                            ),
                        ),
                    ),
                ),
                launch_dir=str(root),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "execution_error")
        self.assertEqual(result.diagnostics[0].code, "runtime.routine.env_non_scalar")


if __name__ == "__main__":
    unittest.main()
