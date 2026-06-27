import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Override, Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import check_workflow


class CheckModeTest(unittest.TestCase):
    def test_check_reports_validation_failure(self) -> None:
        workflow = Workflow(version=1, workflow="open-task", guards=(), steps=())

        result = check_workflow(workflow)

        self.assertEqual(result.mode, Mode.CHECK)
        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertFalse(result.outputs["can_execute"])

    def test_check_reports_resolution_failure(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = check_workflow(workflow)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.unknown_operation")

    def test_check_reports_blocking_guard_without_executing_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.clean_worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        seen_references: list[str] = []

        def probe(resolved_guard, _workflow):
            seen_references.append(resolved_guard.reference)
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

        result = check_workflow(workflow, guard_probe=probe)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.failed_guard, "git.clean_worktree")
        self.assertEqual(result.outputs["blockers"], ["git.clean_worktree"])
        self.assertEqual(seen_references, ["git.clean_worktree"])

    def test_check_reports_success_and_active_profile_metadata(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.clean_worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.view")),),
        )
        profile = Profile(
            name="repo-defaults",
            inputs={"branch": "keep"},
            overrides=(Override(target="shell.command", reason="repo verify policy"),),
        )

        result = check_workflow(workflow, profile=profile)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["can_execute"])
        self.assertEqual(result.outputs["active_profile"], "repo-defaults")
        self.assertEqual(result.outputs["active_overrides"][0]["target"], "shell.command")

    def test_check_reports_expr_guard_as_evaluation_gap_after_resolution(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch != "main"'),), steps=())

        result = check_workflow(workflow)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.guard_expr_evaluation_not_implemented")
        self.assertEqual(result.outputs["checked_guards"], ['git.branch != "main"'])


if __name__ == "__main__":
    unittest.main()
