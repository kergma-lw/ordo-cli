import json
import tempfile
import unittest
from pathlib import Path

from ordo.model.profile import Profile
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, load_workflow_file, plan_workflow, resolve_workflow_references, validate_workflow_text

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


def _preflight_halt_probe(resolved, _workflow):
    if resolved.reference == "gh.issue":
        return OperationResult(
            status="ok",
            summary="issue fetched",
            outputs={"exists": True, "state": "OPEN", "number": 1},
        )
    return OperationResult(status="ok", summary="clean", outputs={"clean": True, "dirty_paths": []})


class GoldenOutputTest(unittest.TestCase):
    @staticmethod
    def _stable_subset(payload):
        return {
            "mode": payload.get("mode"),
            "status": payload.get("status"),
            "failed_guard": payload.get("failed_guard"),
            "failed_step": payload.get("failed_step"),
            "plan": payload.get("plan"),
            "outputs": {
                key: payload.get("outputs", {}).get(key)
                for key in (
                    "can_execute",
                    "blockers",
                    "checked_guards",
                    "executed_steps",
                    "skipped_steps",
                    "analysis_complete",
                    "allowed_state",
                    "execution_allowed",
                    "incomplete_reasons",
                )
                if key in payload.get("outputs", {})
            },
        }

    def test_runtime_mode_outputs_match_goldens(self) -> None:
        blocked = load_workflow_file(Path("examples/samples/blocked-main-branch.yaml"))
        expr_blocked = load_workflow_file(Path("examples/samples/guard-expression-blocked.yaml"))
        inspect = load_workflow_file(Path("examples/samples/inspect-issue.yaml"))
        preflight_halt = load_workflow_file(Path("examples/samples/preflight-halt.yaml"))

        cases = {
            "check_blocked_main_branch.json": check_workflow(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "check_guard_expression_blocked.json": check_workflow(expr_blocked, guard_probe=_expr_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "check_preflight_halt.json": check_workflow(preflight_halt, guard_probe=_preflight_halt_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "plan_inspect_issue.json": plan_workflow(inspect, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "plan_preflight_halt.json": plan_workflow(preflight_halt, guard_probe=_preflight_halt_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "execute_inspect_issue.json": execute_workflow(inspect, guard_probe=_ok_probe, step_executor=_ok_executor, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "explain_blocked_main_branch.json": assess_workflow_readiness(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "explain_guard_expression_blocked.json": assess_workflow_readiness(expr_blocked, guard_probe=_expr_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            "explain_preflight_halt.json": assess_workflow_readiness(preflight_halt, guard_probe=_preflight_halt_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
        }

        for filename, actual in cases.items():
            expected = json.loads((Path("tests/golden") / filename).read_text(encoding="utf-8"))
            self.assertEqual(self._stable_subset(actual), self._stable_subset(expected), filename)


class RuntimeInvariantTest(unittest.TestCase):
    def test_unknown_field_failure_invariant(self) -> None:
        report = validate_workflow_text("version: 0\nworkflow: demo\nextra: true\nblocks:\n  - guards: []\n  - steps: []\n")
        self.assertFalse(report.ok)

    def test_unknown_operation_failure_invariant(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/inspect-issue.yaml"))
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
        workflow = load_workflow_file(Path("examples/samples/inspect-issue.yaml"))
        outputs = [
            check_workflow(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            plan_workflow(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            execute_workflow(workflow, guard_probe=_ok_probe, step_executor=_ok_executor, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
            assess_workflow_readiness(workflow, guard_probe=_ok_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER).to_contract(),
        ]
        for output in outputs:
            json.dumps(output)

    def test_blocked_before_execution_distinct_from_execution_failure(self) -> None:
        blocked = load_workflow_file(Path("examples/samples/blocked-main-branch.yaml"))
        inspect = load_workflow_file(Path("examples/samples/inspect-issue.yaml"))
        blocked_result = execute_workflow(blocked, guard_probe=_blocked_probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        failed_result = execute_workflow(inspect, guard_probe=_ok_probe, step_executor=lambda *_: OperationResult(status="execution_error", summary="boom"), connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(blocked_result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(failed_result.status, RuntimeStatus.EXECUTION_ERROR)

    def test_execution_tree_handoff_reuses_value_state_end_to_end(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="ship", operation=OperationRef("shell.command"), if_="${step.flag.outputs.value}"),)),
            ),
        )

        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        execute_result = execute_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            step_executor=lambda _resolved_step, _workflow: OperationResult(status="ok", summary="ran"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(execute_result.status, RuntimeStatus.OK)
        self.assertEqual(execute_result.outputs["reused_steps"], ["flag"])
        self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "reused_preflight")
        json.dumps(execute_result.to_contract())

    def test_tree_driven_runtime_handles_revalidation_and_divergence_end_to_end(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="inspect", operation=OperationRef("gh.issue"), register="issue"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="ship", operation=OperationRef("shell.command"), if_="${step.issue.outputs.exists}"),)),
            ),
        )

        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": True} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        execute_result = execute_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": False} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            step_executor=lambda _resolved_step, _workflow: OperationResult(status="ok", summary="ran"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(execute_result.status, RuntimeStatus.OK)
        self.assertEqual(execute_result.outputs["execution_tree_mode"], "tree_assisted")
        self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "revalidated")
        self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_status"], "diverged")
        self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][2]["children"][0]["runtime_status"], "skipped_at_run")
        json.dumps(execute_result.to_contract())

    def test_tree_driven_runtime_handles_nested_run_and_profile_switch_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "fragment.yml"
            fragment.write_text(
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: \"echo hi\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                source_path=str(root / "root.yml"),
                launch_dir=str(root),
                steps=(
                    Step(name="switch", profile_switch="frontend"),
                    Step(name="nested", run="fragment.yml", resolved_run_path=str(fragment)),
                ),
            )
            frontend = Profile(name="frontend")
            plan_result = plan_workflow(
                workflow,
                available_profiles={"frontend": frontend},
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )
            execute_result = execute_workflow(
                workflow,
                available_profiles={"frontend": frontend},
                step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
                execution_tree=plan_result.outputs["execution_tree"],
            )

            self.assertEqual(execute_result.status, RuntimeStatus.OK)
            self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "done")
            self.assertEqual(execute_result.outputs["execution_tree"]["blocks"][0]["children"][1]["runtime_status"], "done")
            json.dumps(execute_result.to_contract())


if __name__ == "__main__":
    unittest.main()
