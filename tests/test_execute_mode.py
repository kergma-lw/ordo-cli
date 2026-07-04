import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import execute_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExecuteModeTest(unittest.TestCase):
    def test_execute_preserves_blocked_before_execution(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        def probe(_resolved_guard, _workflow):
            return OperationResult(
                status="guard_failed",
                summary="Dirty worktree",
                diagnostics=(
                    Diagnostic(
                        code="guard.blocked",
                        level="error",
                        message="Worktree is dirty",
                        path=("guards", "0", "uses"),
                    ),
                ),
            )

        result = execute_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode, Mode.EXECUTE)
        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_runs_steps_on_success(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_normalizes_step_failure(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command")),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )
        call_count = 0

        def executor(_resolved_step, _workflow):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OperationResult(status="execution_error", summary="Boom", raw={"stderr": "failed"})
            return OperationResult(status="ok")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.operation_results[-1].raw["stderr"], "failed")

    def test_execute_skips_step_when_condition_is_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, [])
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_runs_step_when_condition_is_true(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": True},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_fails_when_step_condition_cannot_be_evaluated(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.diagnostics[-1].code, "runtime.value.input_missing")


if __name__ == "__main__":
    unittest.main()
