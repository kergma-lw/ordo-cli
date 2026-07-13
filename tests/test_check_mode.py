import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Override, Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class CheckModeTest(unittest.TestCase):
    def test_check_reports_validation_failure(self) -> None:
        workflow = Workflow(version=1, workflow="open-task", guards=(), steps=())

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

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

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.unknown_operation")

    def test_check_reports_blocking_guard_without_executing_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
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

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.failed_guard, "git.worktree")
        self.assertEqual(result.outputs["blockers"], ["git.worktree"])
        self.assertEqual(result.outputs["guard_details"][0]["reference"], "git.worktree")
        self.assertEqual(seen_references, ["git.worktree"])

    def test_check_reports_success_and_active_profile_metadata(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )
        profile = Profile(
            name="repo-defaults",
            inputs={"branch": "keep"},
            overrides=(Override(target="shell.command", reason="repo verify policy"),),
        )

        result = check_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["can_execute"])
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["active_profile"], "repo-defaults")
        self.assertEqual(result.outputs["active_overrides"][0]["target"], "shell.command")

    def test_check_reports_unknown_when_later_guard_region_remains_unchecked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="prepare", operation=OperationRef("gh.issue")),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(result.outputs["can_execute"])
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertFalse(result.outputs["analysis_complete"])
        self.assertIn("relevant_guard_coverage_incomplete", result.outputs["incomplete_reasons"])
        self.assertEqual(result.outputs["relevant_guard_count"], 1)
        self.assertEqual(result.outputs["evaluated_relevant_guard_count"], 0)
        self.assertEqual(result.outputs["unevaluated_relevant_guards"], ["git.worktree"])

    def test_check_surfaces_relevant_guard_coverage(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")), Guard(expr='git.branch.value != "main"')),
            steps=(),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.worktree":
                return OperationResult(status="ok", outputs={"clean": True})
            return OperationResult(status="ok", outputs={"value": "main"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["relevant_guard_count"], 2)
        self.assertEqual(result.outputs["evaluated_relevant_guard_count"], 2)
        self.assertEqual(result.outputs["unevaluated_relevant_guard_count"], 0)
        self.assertEqual(result.outputs["guard_coverage"][0]["status"], "passed")
        self.assertEqual(result.outputs["guard_coverage"][1]["status"], "blocked")
        self.assertIsNotNone(result.preflight_decision)
        assert result.preflight_decision is not None
        self.assertEqual(result.preflight_decision.guard_nodes[0].reference, "git.worktree")
        self.assertEqual(result.preflight_decision.block_nodes[0].block_type, "guards")

    def test_check_marks_verdict_basis_weakened_when_later_action_invalidates_used_observation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='git.branch.value == "main"'),),
            steps=(Step(name="switch", operation=OperationRef("git.branch.switch", with_={"branch": "feature/demo"})),),
        )

        def probe(resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"value": "main"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["verdict_basis_weakened"])
        self.assertIn("git.branch", result.outputs["used_observation_scopes"])
        self.assertIn("git.branch", result.outputs["weakened_observation_scopes"])
        self.assertIn("git.branch", result.outputs["potential_invalidation_scopes"])

    def test_check_uses_family_wide_invalidation_fallback_when_action_has_no_narrow_metadata(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "acme/repo", "issue_number": 1})),),
            steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "acme/repo", "issue_number": 1})),),
        )

        def probe(resolved_guard, _workflow):
            self.assertEqual(resolved_guard.reference, "gh.issue")
            return OperationResult(status="ok", outputs={"state": "OPEN"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertTrue(result.outputs["verdict_basis_weakened"])
        self.assertIn("gh.issue", result.outputs["used_observation_scopes"])
        self.assertIn("gh.*", result.outputs["potential_invalidation_scopes"])

    def test_check_evaluates_expr_guard_with_custom_probe(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.branch":
                return OperationResult(status="ok", outputs={"value": "feature/demo"})
            return OperationResult(status="ok")

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["checked_guards"], ['git.branch.value != "main"'])
        self.assertTrue(result.outputs["guard_details"][0]["trace"])

    def test_check_caches_repeated_expr_probe_reference(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr="git.worktree.clean and git.worktree.clean"),), steps=())
        seen: list[str] = []

        def probe(resolved_guard, _workflow):
            seen.append(resolved_guard.reference)
            return OperationResult(status="ok", outputs={"clean": True})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen, ["git.worktree"])

    def test_check_preserves_probe_failed_vs_guard_false_for_expr(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(resolved_guard, _workflow):
            return OperationResult(status="probe_failed", diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),))

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.operation_results[0].status, "probe_failed")
        self.assertEqual(result.outputs["guard_details"][0]["failure_kind"], "probe_failed")

    def test_check_surfaces_bootstrap_details_from_operation_results(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(OperationRef("git.worktree")),), steps=())

        def probe(resolved_guard, _workflow):
            _ = resolved_guard
            return OperationResult(
                status="not_repository",
                raw={"bootstrap": {"namespace": "git", "status": "not_repository", "context": {}}},
            )

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["bootstrap_details"][0]["namespace"], "git")
        self.assertEqual(result.outputs["bootstrap_details"][0]["status"], "not_repository")

    def test_check_evaluates_not_and_or_with_short_circuit_for_expr(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='not git.worktree.clean or git.branch.value == "release"'),), steps=())
        seen: list[str] = []

        def probe(resolved_guard, _workflow):
            seen.append(resolved_guard.reference)
            if resolved_guard.reference == "git.worktree":
                return OperationResult(status="ok", outputs={"clean": False})
            return OperationResult(status="ok", outputs={"value": "main"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen, ["git.worktree"])


if __name__ == "__main__":
    unittest.main()
