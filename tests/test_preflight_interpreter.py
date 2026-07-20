import unittest
from pathlib import Path
import tempfile

from ordo.model.connector import OperationContract
from ordo.model.runtime import OperationResult
from ordo.model.workflow import OperationRef, Step, Workflow
from ordo.runtime.local_expression_engine.core import ConditionObservationRequest, ConditionObservationResult, ReadOnlyObservationSession
from ordo.runtime.preflight_interpreter import build_preflight_halt, evaluate_preflight_probe_step, evaluate_preflight_step_condition, evaluate_preflight_value_step, expand_preflight_run_step, resolve_preflight_value, store_preflight_register_output
from ordo.runtime.resolution import ResolvedOperation


class PreflightInterpreterTest(unittest.TestCase):
    def test_evaluates_pure_value_step_from_inputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"branch": "main"}, steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["value"], "main")

    def test_reports_structured_error_when_value_step_cannot_be_resolved(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)

        self.assertEqual(result.status, "state_error")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.input_missing")

    def test_stores_value_step_output_for_later_preflight_dataflow(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"branch": "main"}, steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)
        step_results = {}
        store_preflight_register_output("branch", result, step_results=step_results)

        self.assertEqual(step_results["branch"]["outputs"]["value"], "main")

    def test_executes_read_only_probe_steps_through_guard_probe_surface(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step = Step(name="inspect", operation=OperationRef("gh.issue"))
        resolved = ResolvedOperation(
            reference="gh.issue",
            connector_namespace="gh",
            operation=OperationContract(name="issue", kind="probe"),
            source="public",
        )

        def guard_probe(resolved_step, current_workflow):
            self.assertEqual(resolved_step.reference, "gh.issue")
            self.assertIs(current_workflow, workflow)
            return OperationResult(status="ok", outputs={"exists": True})

        result = evaluate_preflight_probe_step(step, resolved, workflow, guard_probe=guard_probe)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["exists"], True)

    def test_rejects_effectful_steps_from_probe_interpretation(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step = Step(name="comment", operation=OperationRef("gh.issue.comment"))
        resolved = ResolvedOperation(
            reference="gh.issue.comment",
            connector_namespace="gh",
            operation=OperationContract(name="issue.comment", kind="action"),
            source="public",
        )

        result = evaluate_preflight_probe_step(step, resolved, workflow, guard_probe=lambda *_args: OperationResult(status="ok"))

        self.assertEqual(result.status, "state_error")

    def test_resolves_value_expressions_from_registered_preflight_value_outputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        first = Step(name="branch", value="main", register="branch")
        second = Step(name="copy", value="${step.branch.outputs.value}", register="copy")

        first_result = evaluate_preflight_value_step(first, workflow)
        step_results = {}
        store_preflight_register_output("branch", first_result, step_results=step_results)
        second_result = evaluate_preflight_value_step(second, workflow, step_results=step_results)

        self.assertEqual(second_result.status, "ok")
        self.assertEqual(second_result.outputs["value"], "main")

    def test_resolves_value_expressions_from_registered_probe_outputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step_results = {
            "issue": {
                "status": "ok",
                "summary": "Loaded issue",
                "outputs": {"exists": True, "number": 42},
            }
        }

        value = resolve_preflight_value("${step.issue.outputs.number}", workflow, step_results=step_results)

        self.assertEqual(value, 42)

    def test_evaluates_true_preflight_step_condition(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"enabled": True}, steps=())
        step = Step(name="inspect", operation=OperationRef("gh.issue"), if_="${inputs.enabled}")

        result = evaluate_preflight_step_condition(step, workflow)

        self.assertEqual(result, True)

    def test_evaluates_false_preflight_step_condition(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"enabled": False}, steps=())
        step = Step(name="inspect", operation=OperationRef("gh.issue"), if_="${inputs.enabled}")

        result = evaluate_preflight_step_condition(step, workflow)

        self.assertEqual(result, False)

    def test_reports_unknown_preflight_step_condition_dependencies(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step = Step(name="inspect", operation=OperationRef("gh.issue"), if_="${inputs.enabled}")

        result = evaluate_preflight_step_condition(step, workflow)

        self.assertEqual(result.code, "runtime.value.input_missing")

    def test_evaluates_preflight_step_condition_through_shared_read_only_engine(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"repository": "owner/repo", "issue_number": 7}, steps=())
        step = Step(
            name="inspect",
            operation=OperationRef("gh.issue"),
            if_='${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).exists and gh.issue( issue_number = inputs.issue_number , repository = inputs.repository ).exists}',
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(status="ok", value=True, reference="gh.issue")

        result = evaluate_preflight_step_condition(step, workflow, observation_session=ReadOnlyObservationSession(observe))

        self.assertEqual(result, True)
        self.assertEqual(count, 1)

    def test_builds_structured_preflight_halt_for_blocked_step(self) -> None:
        step = Step(name="inspect", operation=OperationRef("gh.issue"))

        halt = build_preflight_halt("unresolved_step_argument", step=step, details={"argument": "issue_number"})

        self.assertEqual(
            halt.to_contract(),
            {
                "reason": "unresolved_step_argument",
                "step_name": "inspect",
                "branch_condition": None,
                "details": {"argument": "issue_number"},
            },
        )

    def test_builds_structured_preflight_halt_for_unknown_branch(self) -> None:
        step = Step(name="inspect", operation=OperationRef("gh.issue"), if_="${inputs.enabled}")

        halt = build_preflight_halt(
            "condition_not_computable",
            step=step,
            branch_condition=step.if_,
            details={"depends_on": "inputs.enabled"},
        )

        self.assertEqual(halt.reason, "condition_not_computable")
        self.assertEqual(halt.step_name, "inspect")
        self.assertEqual(halt.branch_condition, "${inputs.enabled}")

    def test_expands_nested_preflight_analyzable_run_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fragment = Path(temp_dir) / "fragment.yml"
            fragment.write_text("steps:\n  - name: switch\n    profile_switch: frontend\n", encoding="utf-8")
            workflow = Workflow(version=0, workflow="demo", blocks=())
            step = Step(name="expand", run="fragment.yml", resolved_run_path=str(fragment))

            expanded = expand_preflight_run_step(step, workflow, block_index=0, step_index=0)

            self.assertIsNotNone(expanded.workflow)
            self.assertIsNone(expanded.halt)
            self.assertEqual(expanded.workflow.workflow, "demo::fragment.yml")

    def test_records_halt_for_unanalyzable_nested_run_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fragment = Path(temp_dir) / "fragment.yml"
            fragment.write_text("steps:\n  - name: comment\n    uses: gh.issue.comment\n", encoding="utf-8")
            workflow = Workflow(version=0, workflow="demo", blocks=())
            step = Step(name="expand", run="fragment.yml", resolved_run_path=str(fragment))

            expanded = expand_preflight_run_step(step, workflow, block_index=0, step_index=0)

            self.assertIsNone(expanded.workflow)
            self.assertEqual(expanded.halt.reason, "run_subtree_requires_effectful_execution")


if __name__ == "__main__":
    unittest.main()
