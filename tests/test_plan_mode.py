import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import plan_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class PlanModeTest(unittest.TestCase):
    def test_plan_describes_checks_and_effectful_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.project.issue.status.set")),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode, Mode.PLAN)
        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.plan.guard_checks, ("git.worktree",))
        self.assertEqual(result.outputs["step_items"][0]["effect"], "effectful")
        self.assertEqual(result.outputs["step_items"][0]["eligibility"], "eligible")

    def test_plan_reports_known_blockers(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
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

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.plan.blockers, ("git.worktree",))
        self.assertEqual(result.outputs["guard_items"][0]["status"], "blocked")
        self.assertEqual(result.outputs["step_items"][0]["eligibility"], "blocked")

    def test_plan_reports_resolution_failure_without_log_scraping(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.outputs["step_items"][0]["reference"], "gh.issue.missing")
        self.assertEqual(result.outputs["step_items"][0]["kind"], "unknown")

    def test_plan_preserves_profile_metadata(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = plan_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["active_profile"], "repo-defaults")
        self.assertTrue(result.outputs["execution_allowed"])

    def test_plan_surfaces_expr_guard_before_runtime_support_exists(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(resolved_guard, _workflow):
            return OperationResult(status="ok", observations={"value": "main"})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["guard_items"][0]["reference"], 'git.branch.value != "main"')
        self.assertEqual(result.outputs["guard_items"][0]["kind"], "expression")
        self.assertEqual(result.outputs["guard_items"][0]["failed_subcondition"], 'git.branch.value != "main"')

    def test_plan_preserves_bootstrap_details_in_outputs(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(OperationRef("git.worktree")),), steps=())

        def probe(resolved_guard, _workflow):
            _ = resolved_guard
            return OperationResult(
                status="not_repository",
                raw={"bootstrap": {"namespace": "git", "status": "not_repository", "context": {}}},
            )

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["bootstrap_details"][0]["namespace"], "git")
        self.assertEqual(result.outputs["bootstrap_details"][0]["status"], "not_repository")


if __name__ == "__main__":
    unittest.main()
