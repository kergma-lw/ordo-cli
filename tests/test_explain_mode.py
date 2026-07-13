import unittest
import tempfile
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import execute_workflow, explain_execution_result, explain_runtime_result, explain_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExplainModeTest(unittest.TestCase):
    def test_explain_reports_guard_block_reason_and_next_action(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='git.branch.value != "main"'),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.branch":
                return OperationResult(status="ok", outputs={"value": "main"})
            return OperationResult(status="ok")

        result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["reason_category"], "guard")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "resolve_blocking_guards")
        self.assertEqual(result.outputs["explanation"]["guard_details"][0]["failed_subcondition"], 'git.branch.value != "main"')

    def test_explain_reports_resolution_problem(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "resolution")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "fix_operation_references")

    def test_explain_reports_ok_state_and_safe_next_action(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["explanation"]["category"], "ok")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "execute_workflow")

    def test_explain_reports_incomplete_preflight_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="prepare", operation=OperationRef("gh.issue")),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["explanation"]["category"], "incomplete")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "complete_preflight_analysis")

    def test_explain_preserves_expanded_run_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-guard.yml"
            fragment.write_text(
                "blocks:\n  - guards:\n      - inputs.enabled == true\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                inputs={"enabled": True},
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="profile-guard.yml", resolved_run_path=str(fragment)),)),
                    GuardBlock(guards=(Guard(expr='inputs.enabled == true'),)),
                ),
            )

            result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.outputs["explanation"]["category"], "ok")
            expanded = [item for item in result.outputs["block_items"] if item.get("expanded_from_run") == "profile-guard.yml"]
            self.assertEqual(len(expanded), 1)

    def test_explain_runtime_result_covers_execution_failure(self) -> None:
        execution_result = RuntimeResult(
            mode="execute",  # type: ignore[arg-type]
            status=RuntimeStatus.EXECUTION_ERROR,
            failed_step="ship",
            outputs={"executed_steps": [], "skipped_steps": ["close"]},
        )

        result = explain_runtime_result(execution_result)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "execution")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_failed_step")

    def test_explain_reports_bootstrap_problem_separately_from_guard_logic(self) -> None:
        runtime_result = RuntimeResult(
            mode="check",  # type: ignore[arg-type]
            status=RuntimeStatus.GUARD_FAILED,
            outputs={
                "blockers": ["git.branch"],
                "guard_details": [{"reference": "git.branch", "failure_kind": "not_repository"}],
                "bootstrap_details": [{"namespace": "git", "status": "not_repository", "context": {}}],
            },
        )

        result = explain_runtime_result(runtime_result)

        self.assertEqual(result.outputs["explanation"]["category"], "bootstrap")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_connector_bootstrap")

    def test_explain_execution_result_wraps_execute_mode(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(), steps=(Step(name="ship", operation=OperationRef("shell.command")),))

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode.value, "explain")
        self.assertIn("explanation", result.outputs)

    def test_explain_execution_result_preserves_step_condition_outcomes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            guards=(),
            steps=(Step(name="ship", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_condition_details"][0]["outcome"], "skipped")
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_false")


if __name__ == "__main__":
    unittest.main()
