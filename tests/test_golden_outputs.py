import json
import unittest
from pathlib import Path

from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.runtime import check_workflow, execute_workflow, explain_workflow, load_workflow_file, plan_workflow, resolve_workflow_references, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


def _blocked_probe(resolved, _workflow):
    if resolved.reference == "git.branch":
        return OperationResult(status="ok", outputs={"value": "main"})
    return OperationResult(status="guard_failed", summary="main branch")


def _ok_probe(_resolved, _workflow):
    return OperationResult(status="ok", summary="clean", outputs={"clean": True, "dirty_paths": []})


def _ok_executor(_resolved, _workflow):
    return OperationResult(status="ok", summary="inspected", outputs={"issue": {"number": 1}})


def _expr_blocked_probe(resolved, _workflow):
    if resolved.reference == "gh.issue":
        return OperationResult(
            status="ok",
            summary="issue fetched",
            outputs={
                "number": 1,
                "state": "DONE",
                "title": "Demo issue",
                "url": "https://example.test/issues/1",
            },
        )
    return OperationResult(status="ok", summary="unused")


class GoldenOutputTest(unittest.TestCase):
    def test_runtime_mode_outputs_match_goldens(self) -> None:
        blocked = load_workflow_file(Path("examples/blocked-main-branch.yaml"))
        expr_blocked = load_workflow_file(Path("examples/guard-expression-blocked.yaml"))
        inspect = load_workflow_file(Path("examples/inspect-issue.yaml"))

        cases = {
            "check_blocked_main_branch.json": check_workflow(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "check_guard_expression_blocked.json": check_workflow(expr_blocked, guard_probe=_expr_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "plan_inspect_issue.json": plan_workflow(inspect, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "execute_inspect_issue.json": execute_workflow(inspect, guard_probe=_ok_probe, step_executor=_ok_executor, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "explain_blocked_main_branch.json": explain_workflow(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "explain_guard_expression_blocked.json": explain_workflow(expr_blocked, guard_probe=_expr_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
        }

        for filename, actual in cases.items():
            expected = json.loads((Path("tests/golden") / filename).read_text(encoding="utf-8"))
            self.assertEqual(actual, expected, filename)


class RuntimeInvariantTest(unittest.TestCase):
    def test_unknown_field_failure_invariant(self) -> None:
        report = validate_workflow_text("version: 0\nworkflow: demo\nextra: true\nguards: []\nsteps: []\n")
        self.assertFalse(report.ok)

    def test_unknown_operation_failure_invariant(self) -> None:
        workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
        workflow = workflow.__class__(
            version=workflow.version,
            workflow=workflow.workflow,
            inputs=workflow.inputs,
            guards=workflow.guards,
            steps=(workflow.steps[0].__class__(name=workflow.steps[0].name, operation=workflow.steps[0].operation.__class__("gh.issue.missing", with_=workflow.steps[0].operation.with_)),),
        )
        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)

    def test_json_serializable_runtime_surfaces_invariant(self) -> None:
        workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
        outputs = [
            check_workflow(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            plan_workflow(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            execute_workflow(workflow, guard_probe=_ok_probe, step_executor=_ok_executor, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            explain_workflow(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
        ]
        for output in outputs:
            json.dumps(output)

    def test_blocked_before_execution_distinct_from_execution_failure(self) -> None:
        blocked = load_workflow_file(Path("examples/blocked-main-branch.yaml"))
        inspect = load_workflow_file(Path("examples/inspect-issue.yaml"))
        blocked_result = execute_workflow(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        failed_result = execute_workflow(inspect, guard_probe=_ok_probe, step_executor=lambda *_: OperationResult(status="execution_error", summary="boom"), connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(blocked_result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(failed_result.status, RuntimeStatus.EXECUTION_ERROR)


if __name__ == "__main__":
    unittest.main()
