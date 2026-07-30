import os
import unittest
import tempfile
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Override, Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from connectors._shared import evaluate_argument_value
from ordo.runtime import check_workflow, load_workflow_text
from ordo.runtime.checking import _build_check_analysis_tree, _project_check_runtime_result

from tests.support import STANDARD_CONNECTOR_PROVIDER


class CheckModeTest(unittest.TestCase):
    def test_check_reports_validation_failure(self) -> None:
        workflow = Workflow(version=1, workflow="open-task", guards=(), steps=())

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode, Mode.CHECK)
        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertFalse(result.outputs["can_execute"])

    def test_check_reports_malformed_adapter_invocation_in_value_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"body": "## Notes\n- ship\n"},
            steps=(
                Step(
                    name="select",
                    value='${markdown["Tasks"].list with{root: inputs.body}',
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "validation.workflow.local_expression.embedded_value.syntax")

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

    def test_check_reports_malformed_text_adapter_invocation_in_value_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"body": "hello\nworld"},
            steps=(
                Step(
                    name="select",
                    value='${text.find("h" with{root: inputs.body}}',
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "validation.workflow.local_expression.embedded_value.syntax")

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

    def test_check_surfaces_inline_fan_out_structure_in_preflight_items(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            inputs={"items": ["one", "two"]},
            steps=(
                Step(
                    name="inspect",
                    for_each="${inputs.items}",
                    steps=(Step(name="copy", value="${item}", register="item_value"),),
                    register="runs",
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertIn(result.status, {RuntimeStatus.OK, RuntimeStatus.GUARD_FAILED})
        fan_out_item = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "inspect")
        self.assertEqual(fan_out_item["body_kind"], "inline_repeated_steps")
        self.assertEqual(fan_out_item["fan_out"], {"enabled": True})

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

    def test_check_keeps_guard_verdict_stable_when_later_action_invalidates_same_scope(self) -> None:
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
        self.assertFalse(result.outputs["verdict_basis_weakened"])
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

        self.assertFalse(result.outputs["verdict_basis_weakened"])
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

    def test_check_records_canonical_observed_probe_calls_for_guard_expressions(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"'),),
            steps=(),
            inputs={"repository": "acme/repo", "issue_number": 7},
        )

        def probe(resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"state": "OPEN"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(
            result.outputs["guard_details"][0]["observations"],
            [
                {
                    "probe": "gh.issue",
                    "with": {
                        "repository": {"expression": "inputs.repository"},
                        "issue_number": {"expression": "inputs.issue_number"},
                    },
                    "fields": ["state"],
                }
            ],
        )

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

    def test_check_surfaces_probe_field_missing_for_expr_guard(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(_resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"other": "feature/demo"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.operation_results[0].status, "probe_failed")
        self.assertEqual(result.operation_results[0].diagnostics[0].code, "guard.probe_field_missing")
        self.assertEqual(result.outputs["guard_details"][0]["failed_subcondition"], "git.branch.value")

    def test_check_reports_non_boolean_guard_result_as_guard_error(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"title": "demo"}, guards=(Guard(expr="inputs.title"),), steps=())

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.operation_results[0].status, "execution_error")
        self.assertEqual(result.operation_results[0].diagnostics[-1].code, "runtime.guard.result_type")
        self.assertEqual(result.outputs["guard_details"][0]["failure_kind"], "result_type")
        self.assertEqual(result.failed_guard, "inputs.title")

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

    def test_check_applies_deterministic_profile_switch_before_later_guards(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repo_kind": {}},
            blocks=(
                StepBlock(steps=(Step(name="switch-profile", profile_switch="frontend"),)),
                GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
            ),
        )
        profiles = {"frontend": Profile(name="frontend", inputs={"repo_kind": "frontend"})}

        result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(result.outputs["block_items"][0]["status"], "context_applied")
        self.assertEqual(result.outputs["block_items"][1]["active_profile"], "frontend")
        assert result.preflight_decision is not None
        self.assertEqual(result.preflight_decision.block_nodes[1].active_profile, "frontend")

    def test_check_uses_profile_working_directory_after_static_profile_switch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="switch-profile", profile_switch="frontend"),)),
                GuardBlock(guards=(Guard(OperationRef("git.branch")),)),
            ),
        )
        profiles = {"frontend": Profile(name="frontend")}

        def probe(resolved_guard, _workflow):
            value = Path.cwd().name
            return OperationResult(
                status="ok" if value == "frontend" else "guard_failed",
                summary="cwd probe",
                outputs={"value": value},
                raw={
                    "trace": [
                        {"expr": "git.branch", "kind": "probe", "reference": "git.branch", "status": "ok", "value": value}
                    ]
                },
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_dir = root / "compose"
            frontend_dir = root / "frontend"
            compose_dir.mkdir()
            frontend_dir.mkdir()
            previous = Path.cwd()
            os.chdir(compose_dir)
            try:
                result = check_workflow(
                    workflow,
                    available_profiles=profiles,
                    profile_working_directories={"frontend": frontend_dir},
                    guard_probe=probe,
                    connector_provider=STANDARD_CONNECTOR_PROVIDER,
                )
            finally:
                os.chdir(previous)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["active_profile"], "frontend")

    def test_check_keeps_trailing_profile_switch_after_effectful_preflight_halt(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="fetch-compose", operation=OperationRef("git.sync.fetch", with_={"remote": "origin"})),
                        Step(name="switch-profile", profile_switch="backend"),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.branch")),)),
            ),
        )
        profiles = {"backend": Profile(name="backend")}

        def probe(resolved_guard, _workflow):
            value = Path.cwd().name
            return OperationResult(
                status="ok" if value == "backend" else "guard_failed",
                summary="cwd probe",
                outputs={"value": value},
                raw={
                    "trace": [
                        {"expr": "git.branch", "kind": "probe", "reference": "git.branch", "status": "ok", "value": value}
                    ]
                },
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compose_dir = root / "compose"
            backend_dir = root / "backend"
            compose_dir.mkdir()
            backend_dir.mkdir()
            previous = Path.cwd()
            os.chdir(compose_dir)
            try:
                result = check_workflow(
                    workflow,
                    available_profiles=profiles,
                    profile_working_directories={"backend": backend_dir},
                    guard_probe=probe,
                    connector_provider=STANDARD_CONNECTOR_PROVIDER,
                )
            finally:
                os.chdir(previous)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertFalse(result.outputs["analysis_complete"])
        self.assertIn("effectful_step_encountered", result.outputs["incomplete_reasons"])
        self.assertIn("git.branch", result.outputs["checked_guards"])
        self.assertEqual(result.outputs["active_profile"], "backend")
        self.assertEqual(result.outputs["unevaluated_relevant_guard_count"], 0)

    def test_check_keeps_profile_switch_unknown_when_profile_cannot_be_resolved(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"profile": {}, "repo_kind": {}},
            blocks=(
                StepBlock(steps=(Step(name="switch-profile", profile_switch="${inputs.profile}"),)),
                GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertIn("profile_switch_not_resolvable_from_current_knowledge", result.outputs["incomplete_reasons"])

    def test_check_evaluates_guard_pipeline_filters(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="set-task-estimate",
            inputs={"estimate": 1},
            declared_inputs={"estimate": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr="inputs.estimate | is_number"),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["evaluated_relevant_guard_count"], 1)

    def test_check_expands_static_run_fragment_and_continues_to_later_guards(self) -> None:
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

            result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertEqual(result.outputs["evaluated_relevant_guard_count"], 2)
            expanded = [item for item in result.outputs["block_items"] if item.get("expanded_from_run") == "profile-guard.yml"]
            self.assertEqual(len(expanded), 1)
            self.assertEqual(expanded[0]["type"], "guards")

    def test_check_rejects_undeclared_root_input_inside_run_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-guard.yml"
            fragment.write_text(
                "blocks:\n  - guards:\n      - inputs.size == \"L\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="profile-guard.yml", resolved_run_path=str(fragment)),)),
                ),
            )

            result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
            self.assertEqual(result.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")

    def test_check_accepts_declared_root_input_used_inside_run_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-guard.yml"
            fragment.write_text(
                "blocks:\n  - guards:\n      - inputs.size == \"L\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                inputs={"size": "L"},
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="profile-guard.yml", resolved_run_path=str(fragment)),)),
                ),
            )

            result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")

    def test_check_propagates_profile_context_from_expanded_run_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "switch.yml"
            fragment.write_text(
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                declared_inputs={"repo_kind": {}},
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="switch.yml", resolved_run_path=str(fragment)),)),
                    GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
                ),
            )
            profiles = {"frontend": Profile(name="frontend", inputs={"repo_kind": "frontend"})}

            result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertEqual(result.outputs["active_profile"], "frontend")
            self.assertEqual(result.outputs["block_items"][-1]["active_profile"], "frontend")

    def test_check_uses_read_only_preflight_steps_to_reach_later_guards(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"run_effectful": False},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),
                        Step(name="copy-flag", value="${step.issue.outputs.exists}", register="issue_exists"),
                        Step(name="comment", operation=OperationRef("gh.issue.close"), if_="${inputs.run_effectful}"),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )
        seen: list[str] = []

        def probe(resolved_guard, _workflow):
            seen.append(resolved_guard.reference)
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertEqual(seen, ["gh.issue", "git.worktree"])
        self.assertEqual(result.outputs["block_items"][0]["status"], "preflight_interpreted")
        self.assertEqual(result.outputs["block_items"][0]["interpreted_steps"], ["load-issue", "copy-flag"])
        self.assertEqual(result.outputs["block_items"][0]["skipped_steps"], ["comment"])

    def test_check_halts_when_effectful_step_is_reachable_during_preflight(self) -> None:
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
            self.assertEqual(resolved_guard.reference, "gh.issue")
            return OperationResult(status="ok", outputs={"exists": True})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertIn("effectful_step_encountered", result.outputs["incomplete_reasons"])
        self.assertEqual(result.outputs["block_items"][0]["status"], "preflight_halted")
        self.assertEqual(result.outputs["block_items"][0]["preflight_halt"]["reason"], "effectful_step_encountered")
        self.assertEqual(result.outputs["unevaluated_relevant_guards"], ["git.worktree"])
        self.assertEqual(
            result.outputs["preflight_step_items"][1]["action_call"],
            {"reference": "gh.issue.close", "with": {}},
        )

    def test_check_reports_strong_preflight_support_when_recommended_observations_match_exactly(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"branch": "feature/demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="branch", operation=OperationRef("git.branch"), register="branch"),
                        Step(name="upstream", operation=OperationRef("git.upstream"), register="upstream"),
                        Step(name="branch_name", value="${inputs.branch}", register="branch_name"),
                        Step(
                            name="range",
                            operation=OperationRef(
                                "git.range",
                                with_={"base": "@{upstream}", "head": "${step.branch_name.outputs.value}"},
                            ),
                            register="range",
                        ),
                        Step(
                            name="push",
                            operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"}),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            outputs = {
                "git.branch": {"value": "feature/demo"},
                "git.upstream": {"configured": True, "branch": "feature/demo", "remote": "origin"},
                "git.range": {"ahead_count": 1, "behind_count": 0},
                "git.worktree": {"clean": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][4]["preflight_support"]
        self.assertEqual(support["strength"], "strong")
        self.assertEqual(len(support["matched_observations"]), 3)
        self.assertEqual(support["missing_observations"], [])

    def test_check_keeps_preflight_observation_matching_exact_without_expression_guessing(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"branch": "feature/demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="branch", operation=OperationRef("git.branch"), register="branch"),
                        Step(name="upstream", operation=OperationRef("git.upstream"), register="upstream"),
                        Step(name="branch_name", value="${inputs.branch}", register="branch_name"),
                        Step(
                            name="range",
                            operation=OperationRef(
                                "git.range",
                                with_={"base": "@{upstream}", "head": "${inputs.branch}"},
                            ),
                            register="range",
                        ),
                        Step(
                            name="push",
                            operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"}),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            outputs = {
                "git.branch": {"value": "feature/demo"},
                "git.upstream": {"configured": True, "branch": "feature/demo", "remote": "origin"},
                "git.range": {"ahead_count": 1, "behind_count": 0},
                "git.worktree": {"clean": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][4]["preflight_support"]
        self.assertEqual(support["strength"], "partial")
        self.assertEqual(len(support["matched_observations"]), 2)
        self.assertEqual(
            support["missing_observations"],
            [
                {
                    "probe": "git.range",
                    "with": {"base": "@{upstream}", "head": {"expression": "step.branch_name.outputs.value"}},
                    "fields": [],
                }
            ],
        )

    def test_check_uses_shared_read_only_engine_for_preflight_values_and_conditions(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "owner/repo", "issue_number": 7, "run_effectful": False},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="load-exists",
                            value="${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).exists}",
                            register="issue_exists",
                        ),
                        Step(
                            name="comment",
                            operation=OperationRef("gh.issue.close"),
                            if_="${gh.issue( issue_number = inputs.issue_number , repository = inputs.repository ).exists and inputs.run_effectful}",
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )
        seen: list[str] = []

        def probe(resolved_guard, _workflow):
            seen.append(resolved_guard.reference)
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertEqual(seen, ["gh.issue", "git.worktree"])
        self.assertEqual(result.outputs["block_items"][0]["interpreted_steps"], ["load-exists"])
        self.assertEqual(result.outputs["block_items"][0]["skipped_steps"], ["comment"])

    def test_check_records_canonical_observed_probe_calls_for_preflight_probe_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 7},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="load-issue",
                            operation=OperationRef(
                                "gh.issue",
                                with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"},
                            ),
                            register="issue",
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = check_workflow(
            workflow,
            guard_probe=probe,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(
            result.outputs["preflight_step_items"][0]["observations"],
            [
                {
                    "probe": "gh.issue",
                    "with": {
                        "repository": {"expression": "inputs.repository"},
                        "issue_number": {"expression": "inputs.issue_number"},
                    },
                    "fields": [],
                }
            ],
        )

    def test_check_resolves_probe_metadata_for_guard_call_with_adapter_bound_nested_probe(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
  project_id: PVT_demo
let:
  story_task_refs: 'text.lines with{root: gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}'
blocks:
  - guards:
      - 'gh.project.items.details(project_id=inputs.project_id, content_refs=story_task_refs, filters=[{field:"State", value:"OPEN"}]).count == 0'
  - steps: []
"""
        )
        seen: list[str] = []
        captured: dict[str, object] = {}

        def probe(resolved_guard, _workflow):
            seen.append(resolved_guard.reference)
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"body": "owner/repo#7\nowner/repo#8"})
            if resolved_guard.reference == "gh.project.items.details":
                captured.update({name: evaluate_argument_value(value, _workflow) for name, value in resolved_guard.arguments})
                return OperationResult(status="ok", outputs={"count": 0, "items": []})
            return OperationResult(status="ok", outputs={})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen, ["gh.issue", "gh.project.items.details"])
        self.assertEqual(captured["content_refs"], ["owner/repo#7", "owner/repo#8"])
        self.assertEqual(captured["filters"], [{"field": "State", "value": "OPEN"}])

    def test_check_preserves_later_action_call_shape_when_missing_input_halts_preflight(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"branch": "string"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="branch_name", value="${inputs.branch}", register="branch_name"),
                        Step(
                            name="push",
                            operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"}),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertIn("read_only_step_failed", result.outputs["incomplete_reasons"])
        self.assertEqual(result.outputs["preflight_step_items"][1]["status"], "pending")
        self.assertEqual(
            result.outputs["preflight_step_items"][1]["action_call"],
            {
                "reference": "git.sync.push",
                "with": {"branch": {"expression": "step.branch_name.outputs.value"}},
            },
        )

    def test_check_renders_missing_preflight_observations_without_input_values_when_step_shape_is_known(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"branch": "string"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="branch_name", value="${inputs.branch}", register="branch_name"),
                        Step(
                            name="push",
                            operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"}),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][1]["preflight_support"]
        self.assertEqual(support["strength"], "weak")
        self.assertEqual(support["matched_observations"], [])
        self.assertEqual(
            support["missing_observations"],
            [
                {"probe": "git.branch", "with": {}, "fields": []},
                {"probe": "git.upstream", "with": {}, "fields": []},
                {
                    "probe": "git.range",
                    "with": {"base": "@{upstream}", "head": {"expression": "step.branch_name.outputs.value"}},
                    "fields": [],
                },
            ],
        )

    def test_check_keeps_structural_recommendations_expression_shaped_under_missing_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "issue_number": "number", "project_id": "string", "field": "string", "value": "json"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-target", value="${inputs.repository}", register="repo_name"),
                        Step(
                            name="set-field",
                            operation=OperationRef(
                                "gh.project.issue.field_number.set",
                                with_={
                                    "repository": "${step.repo_name.outputs.value}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "${inputs.field}",
                                    "value": "${inputs.value}",
                                },
                            ),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][1]["preflight_support"]
        self.assertEqual(
            support["missing_observations"],
            [
                {
                    "probe": "gh.project.issue",
                    "with": {
                        "repository": {"expression": "step.repo_name.outputs.value"},
                        "issue_number": {"expression": "inputs.issue_number"},
                        "project_id": {"expression": "inputs.project_id"},
                    },
                    "fields": ["exists"],
                },
                {
                    "probe": "gh.project.field",
                    "with": {
                        "project_id": {"expression": "inputs.project_id"},
                        "field": {"expression": "inputs.field"},
                    },
                    "fields": ["exists"],
                },
            ],
        )

    def test_check_recommends_missing_observations_for_guardless_effectful_block(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "issue_number": "number", "project_id": "string"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "In review",
                                },
                            ),
                        ),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["preflight_step_items"][0]["status"], "pending")
        support = result.outputs["preflight_step_items"][0]["preflight_support"]
        self.assertEqual(support["strength"], "weak")
        self.assertEqual(
            support["missing_observations"],
            [
                {
                    "probe": "gh.project.issue",
                    "with": {
                        "repository": {"expression": "inputs.repository"},
                        "issue_number": {"expression": "inputs.issue_number"},
                        "project_id": {"expression": "inputs.project_id"},
                    },
                    "fields": ["exists"],
                },
                {
                    "probe": "gh.project.field",
                    "with": {"project_id": {"expression": "inputs.project_id"}, "field": "Status"},
                    "fields": ["exists"],
                },
                {
                    "probe": "gh.project.field.option",
                    "with": {"project_id": {"expression": "inputs.project_id"}, "field": "Status", "option": "In review"},
                    "fields": ["exists"],
                },
            ],
        )

    def test_check_analysis_tree_preserves_missing_input_structural_evidence(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "issue_number": "number", "project_id": "string", "field": "string", "value": "json"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-target", value="${inputs.repository}", register="repo_name"),
                        Step(
                            name="set-field",
                            operation=OperationRef(
                                "gh.project.issue.field_number.set",
                                with_={
                                    "repository": "${step.repo_name.outputs.value}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "${inputs.field}",
                                    "value": "${inputs.value}",
                                },
                            ),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        analysis = _build_check_analysis_tree(
            workflow=workflow,
            active_profile=None,
            current_profile=None,
            available_profiles=None,
            active_overrides=(),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            guard_probe=None,
        )

        self.assertFalse(isinstance(analysis, RuntimeResult))
        self.assertEqual(analysis.incomplete_reasons, ("read_only_step_failed", "relevant_guard_coverage_incomplete"))
        self.assertEqual(analysis.block_items[0]["status"], "preflight_halted")
        self.assertEqual(
            analysis.preflight_step_items[1]["preflight_support"]["missing_observations"],
            [
                {
                    "probe": "gh.project.issue",
                    "with": {
                        "repository": {"expression": "step.repo_name.outputs.value"},
                        "issue_number": {"expression": "inputs.issue_number"},
                        "project_id": {"expression": "inputs.project_id"},
                    },
                    "fields": ["exists"],
                },
                {
                    "probe": "gh.project.field",
                    "with": {
                        "project_id": {"expression": "inputs.project_id"},
                        "field": {"expression": "inputs.field"},
                    },
                    "fields": ["exists"],
                },
            ],
        )

    def test_check_runtime_projection_keeps_preflight_support_non_blocking(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"branch": "feature/demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="branch", operation=OperationRef("git.branch"), register="branch"),
                        Step(name="upstream", operation=OperationRef("git.upstream"), register="upstream"),
                        Step(name="branch_name", value="${inputs.branch}", register="branch_name"),
                        Step(
                            name="range",
                            operation=OperationRef(
                                "git.range",
                                with_={"base": "@{upstream}", "head": "${step.branch_name.outputs.value}"},
                            ),
                            register="range",
                        ),
                        Step(
                            name="push",
                            operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"}),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            outputs = {
                "git.branch": {"value": "feature/demo"},
                "git.upstream": {"configured": True, "branch": "feature/demo", "remote": "origin"},
                "git.range": {"ahead_count": 1, "behind_count": 0},
                "git.worktree": {"clean": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        analysis = _build_check_analysis_tree(
            workflow=workflow,
            active_profile=None,
            current_profile=None,
            available_profiles=None,
            active_overrides=(),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            guard_probe=probe,
        )

        self.assertFalse(isinstance(analysis, RuntimeResult))
        result = _project_check_runtime_result(analysis)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "unknown")
        self.assertEqual(result.outputs["preflight_step_items"][4]["preflight_support"]["strength"], "strong")
        self.assertIn("effectful_step_encountered", result.outputs["incomplete_reasons"])

    def test_check_analysis_tree_classifies_control_effect_and_unused_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="review-inputs",
            declared_inputs={
                "profile": {},
                "repository": {},
                "unused": {},
            },
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'),)),
                StepBlock(
                    steps=(
                        Step(
                            name="inspect",
                            operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7}),
                        ),
                    )
                ),
            ),
        )

        analysis = _build_check_analysis_tree(
            workflow=workflow,
            active_profile=None,
            current_profile=None,
            available_profiles=None,
            active_overrides=(),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            guard_probe=None,
        )

        self.assertFalse(isinstance(analysis, RuntimeResult))
        classifications = {item["input"]: item for item in analysis.input_usages}

        self.assertEqual(classifications["profile"]["classification"], "control_input")
        self.assertEqual(classifications["profile"]["evidence"][0]["site_kind"], "guard_expr")
        self.assertEqual(classifications["repository"]["classification"], "effect_target_input")
        self.assertEqual(classifications["repository"]["evidence"][0]["site_kind"], "operation_target")
        self.assertEqual(classifications["unused"]["classification"], "unused_input")
        self.assertEqual(classifications["unused"]["evidence"], [])

    def test_check_analysis_tree_classifies_publish_inputs_as_contract_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish-inputs",
            declared_inputs={"repository": {}, "profile": {}},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="publish",
                            publish={"repository": "${inputs.repository}", "profile": "${inputs.profile}"},
                        ),
                    )
                ),
            ),
        )

        analysis = _build_check_analysis_tree(
            workflow=workflow,
            active_profile=None,
            current_profile=None,
            available_profiles=None,
            active_overrides=(),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            guard_probe=None,
        )

        self.assertFalse(isinstance(analysis, RuntimeResult))
        classifications = {item["input"]: item for item in analysis.input_usages}
        self.assertEqual(classifications["repository"]["classification"], "contract_input")
        self.assertEqual(classifications["profile"]["classification"], "contract_input")


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
