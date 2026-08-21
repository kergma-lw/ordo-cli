import json
import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow


class ContractShapeTest(unittest.TestCase):
    def test_workflow_contract_matches_stable_shape(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "repo/name", "issue_number": 1},
            state_needs={"task_memory": {}},
            blocks=(
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(
                    steps=(
                        Step(
                            name="inspect-issue",
                            operation=OperationRef("gh.issue", with_={"repository": "repo/name", "issue_number": 1}),
                            register="issue",
                        ),
                    )
                ),
            ),
        )

        self.assertEqual(
            workflow.to_contract(),
            {
                "version": 0,
                "workflow": "open-task",
                "inputs": {
                    "repository": {"required": False, "default": "repo/name"},
                    "issue_number": {"required": False, "default": 1},
                },
                "let": {},
                "state_needs": {"task_memory": {}},
                "blocks": [
                    {"guards": [{"uses": "git.worktree", "with": {}}]},
                    {
                        "steps": [
                            {
                                "name": "inspect-issue",
                                "uses": "gh.issue",
                                "with": {"repository": "repo/name", "issue_number": 1},
                                "register": "issue",
                            }
                        ]
                    },
                ],
            },
        )

    def test_workflow_contract_allows_expr_guard_shape(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", blocks=(GuardBlock(guards=(Guard(expr='git.branch != "main"'),)),))

        self.assertEqual(
            workflow.to_contract(),
            {
                "version": 0,
                "workflow": "open-task",
                "inputs": {},
                "let": {},
                "state_needs": {},
                "blocks": [{"guards": ['git.branch != "main"']}],
            },
        )

    def test_step_contract_allows_builtin_state_forms(self) -> None:
        state_set = Step(name="remember-branch", state_set={"state.task_memory[inputs.issue_ref].branch": "${inputs.branch}"})
        state_delete = Step(name="forget-branch", state_delete="state.task_memory[inputs.issue_ref].branch")

        self.assertEqual(
            state_set.to_contract(),
            {
                "name": "remember-branch",
                "state_set": {"state.task_memory[inputs.issue_ref].branch": "${inputs.branch}"},
            },
        )
        self.assertEqual(
            state_delete.to_contract(),
            {
                "name": "forget-branch",
                "state_delete": "state.task_memory[inputs.issue_ref].branch",
            },
        )

    def test_step_contract_allows_value_form(self) -> None:
        value_step = Step(name="compute-branch", value={"format": "{}/{}", "args": ["${inputs.type | lower}", "${inputs.issue_number}"]}, register="branch")

        self.assertEqual(
            value_step.to_contract(),
            {
                "name": "compute-branch",
                "value": {"format": "{}/{}", "args": ["${inputs.type | lower}", "${inputs.issue_number}"]},
                "register": "branch",
            },
        )

    def test_step_contract_preserves_optional_if_field(self) -> None:
        operation_step = Step(name="inspect", operation=OperationRef("gh.issue"), if_='${inputs.enabled}')
        state_step = Step(name="remember", state_set={"state.task_memory[inputs.issue_ref].branch": "${inputs.branch}"}, if_='${inputs.persist}')

        self.assertEqual(operation_step.to_contract()["if"], '${inputs.enabled}')
        self.assertEqual(state_step.to_contract()["if"], '${inputs.persist}')

    def test_step_contract_preserves_structured_if_field(self) -> None:
        operation_step = Step(name="inspect", operation=OperationRef("gh.issue"), if_={"all": ["inputs.enabled", {"not": "inputs.blocked"}]})

        self.assertEqual(operation_step.to_contract()["if"], {"all": ["inputs.enabled", {"not": "inputs.blocked"}]})

    def test_step_contract_preserves_gate_on_fail_field(self) -> None:
        operation_step = Step(
            name="inspect",
            operation=OperationRef("gh.issue"),
            gate={"all": ["step.issue.outputs.exists"]},
            gate_on_fail={"issue_number": "inputs.issue_number", "exists": "step.issue.outputs.exists"},
        )

        self.assertEqual(
            operation_step.to_contract()["gate"],
            {
                "all": ["step.issue.outputs.exists"],
                "on_fail": {"issue_number": "inputs.issue_number", "exists": "step.issue.outputs.exists"},
            },
        )

    def test_run_step_contract_preserves_if_and_with(self) -> None:
        run_step = Step(name="comment-and-status", run="github/comment-and-set-status", if_="${step.issue.outputs.open}", run_with={"comment": "hello"})

        self.assertEqual(
            run_step.to_contract(),
            {
                "name": "comment-and-status",
                "run": "github/comment-and-set-status",
                "if": "${step.issue.outputs.open}",
                "with": {"comment": "hello"},
            },
        )

    def test_runtime_result_contract_is_json_serializable(self) -> None:
        result = RuntimeResult(
            mode=Mode.PLAN,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=(
                Diagnostic(
                    code="guard.blocked",
                    level="error",
                    message="Worktree is dirty",
                    path=("guards", "0"),
                    details={"uses": "git.worktree"},
                ),
            ),
            plan=ExecutionPlan(
                guard_checks=("git.worktree",),
                step_names=("inspect-issue",),
                blockers=("git.worktree",),
            ),
            outputs={"can_execute": False},
            operation_results=(
                OperationResult(
                    status="guard_failed",
                    summary="Dirty worktree",
                    outputs={"dirty": True},
                ),
            ),
            failed_guard="git.worktree",
            failed_step=None,
        )

        contract = result.to_contract()

        self.assertEqual(contract["mode"], "plan")
        self.assertEqual(contract["status"], "guard_failed")
        self.assertEqual(contract["failed_guard"], "git.worktree")
        self.assertIsNone(contract["failed_step"])
        self.assertEqual(contract["plan"]["blockers"], ["git.worktree"])
        json.dumps(contract)


if __name__ == "__main__":
    unittest.main()
