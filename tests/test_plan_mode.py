import unittest
import tempfile
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
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

    def test_plan_does_not_upgrade_unknown_check_result_to_allowed(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="prepare", operation=OperationRef("gh.issue")),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(result.outputs["execution_allowed"])
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertFalse(result.outputs["guard_items"][0]["evaluated"])
        self.assertEqual(result.outputs["guard_items"][0]["unknown_reason"], "guard_not_evaluated")
        self.assertIsNotNone(result.preflight_decision)

    def test_plan_preserves_expanded_run_structure(self) -> None:
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

            result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            expanded = [item for item in result.outputs["block_items"] if item.get("expanded_from_run") == "profile-guard.yml"]
            self.assertEqual(result.outputs["execution_allowed"], True)
            self.assertEqual(len(expanded), 1)

    def test_plan_surfaces_expr_guard_before_runtime_support_exists(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"value": "main"})

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

    def test_plan_marks_conditional_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue"), if_="${inputs.enabled}"),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertTrue(result.outputs["step_items"][0]["conditional"])
        self.assertEqual(result.outputs["step_items"][0]["condition"], "${inputs.enabled}")
        self.assertEqual(result.outputs["step_items"][0]["condition_status"], "unknown")

    def test_plan_surfaces_preflight_step_classification(self) -> None:
        cases = [
            (Step(name="probe", operation=OperationRef("gh.issue")), "read_only_analyzable"),
            (Step(name="value", value=True, register="enabled"), "read_only_analyzable"),
            (Step(name="switch", profile_switch="frontend"), "context_only"),
            (Step(name="run-fragment", run="fragment.yml"), "read_only_unanalyzable"),
            (Step(name="write-state", state_set={"state.shared_state.flag": True}), "effectful"),
        ]

        for step, expected in cases:
            workflow = Workflow(version=0, workflow="open-task", guards=(), steps=(step,))
            result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
            self.assertEqual(result.outputs["step_items"][0]["preflight_classification"], expected)

    def test_plan_keeps_unknown_preflight_classification_for_unresolved_operations(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_items"][0]["preflight_classification"], "unknown")

    def test_plan_preserves_preflight_interpretation_details(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"run_effectful": True},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),
                        Step(name="comment", operation=OperationRef("gh.issue.close"), if_="${inputs.run_effectful}"),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", summary="Loaded issue", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["preflight_step_items"][0]["status"], "interpreted")
        self.assertEqual(result.outputs["preflight_step_items"][0]["outputs"], {"exists": True})
        self.assertEqual(result.outputs["preflight_step_items"][0]["observation_scopes"], ["gh.issue"])
        self.assertIn("Loaded", result.outputs["preflight_step_items"][0]["summary"])
        self.assertEqual(result.outputs["preflight_step_items"][1]["status"], "halted")
        self.assertEqual(result.outputs["preflight_halts"][0]["reason"], "effectful_step_encountered")
        self.assertEqual(
            result.outputs["preflight_registers"],
            {
                "issue": {
                    "status": "ok",
                    "summary": "Loaded issue",
                    "outputs": {"exists": True},
                }
            },
        )
        self.assertEqual(result.outputs["preflight_step_results"], result.outputs["preflight_registers"])
        self.assertEqual(result.outputs["preflight_step_items"][0]["condition_status"], None)
        self.assertEqual(result.outputs["preflight_step_items"][1]["condition_status"], "true")
        self.assertEqual(result.outputs["step_items"][1]["condition_status"], "true")

    def test_plan_reports_false_condition_status_for_skipped_preflight_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"run_effectful": False},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),
                        Step(name="comment", operation=OperationRef("gh.issue.close"), if_="${inputs.run_effectful}"),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["preflight_step_items"][1]["status"], "skipped")
        self.assertEqual(result.outputs["preflight_step_items"][1]["condition_status"], "false")

    def test_plan_surfaces_step_launcher_selection(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("shell.command"), launcher="shell_frontend"),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_items"][0]["launcher"], "shell_frontend")


if __name__ == "__main__":
    unittest.main()
