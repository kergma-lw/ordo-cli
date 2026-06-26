import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import plan_workflow


class PlanModeTest(unittest.TestCase):
    def test_plan_describes_checks_and_effectful_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.clean_worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.project_set_status")),),
        )

        result = plan_workflow(workflow)

        self.assertEqual(result.mode, Mode.PLAN)
        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.plan.guard_checks, ("git.clean_worktree",))
        self.assertEqual(result.outputs["step_items"][0]["effect"], "effectful")
        self.assertEqual(result.outputs["step_items"][0]["eligibility"], "eligible")

    def test_plan_reports_known_blockers(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.clean_worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.view")),),
        )

        def probe(resolved_guard, _workflow):
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

        result = plan_workflow(workflow, guard_probe=probe)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.plan.blockers, ("git.clean_worktree",))
        self.assertEqual(result.outputs["guard_items"][0]["status"], "blocked")
        self.assertEqual(result.outputs["step_items"][0]["eligibility"], "blocked")

    def test_plan_reports_resolution_failure_without_log_scraping(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = plan_workflow(workflow)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.outputs["step_items"][0]["reference"], "gh.issue.missing")
        self.assertEqual(result.outputs["step_items"][0]["kind"], "unknown")

    def test_plan_preserves_profile_metadata(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.clean_worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.view")),),
        )
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = plan_workflow(workflow, profile=profile)

        self.assertEqual(result.outputs["active_profile"], "repo-defaults")
        self.assertTrue(result.outputs["execution_allowed"])

    def test_plan_surfaces_expr_guard_before_runtime_support_exists(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch != "main"'),), steps=())

        result = plan_workflow(workflow)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.outputs["guard_items"][0]["reference"], 'git.branch != "main"')
        self.assertEqual(result.outputs["guard_items"][0]["kind"], "probe_or_expr")


if __name__ == "__main__":
    unittest.main()
