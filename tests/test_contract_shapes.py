import json
import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow


class ContractShapeTest(unittest.TestCase):
    def test_workflow_contract_matches_stable_shape(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"issue_ref": "repo#1"},
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(
                Step(
                    name="inspect-issue",
                    operation=OperationRef("gh.issue", with_={"issue_ref": "repo#1"}),
                ),
            ),
        )

        self.assertEqual(
            workflow.to_contract(),
            {
                "version": 0,
                "workflow": "open-task",
                "inputs": {"issue_ref": "repo#1"},
                "guards": [{"uses": "git.worktree", "with": {}}],
                "steps": [
                    {
                        "name": "inspect-issue",
                        "uses": "gh.issue",
                        "with": {"issue_ref": "repo#1"},
                    }
                ],
            },
        )

    def test_workflow_contract_allows_expr_guard_shape(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch != "main"'),), steps=())

        self.assertEqual(
            workflow.to_contract(),
            {
                "version": 0,
                "workflow": "open-task",
                "inputs": {},
                "guards": ['git.branch != "main"'],
                "steps": [],
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
                    observations={"dirty": True},
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
