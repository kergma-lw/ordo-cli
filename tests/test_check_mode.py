import os
import tempfile
import textwrap
import unittest
from dataclasses import replace
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

    def test_check_reports_gate_failure_and_all_failed_clauses(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="ready-a", value=False, register="ready_a"),
                        Step(name="ready-b", value=False, register="ready_b"),
                        Step(
                            name="mutate",
                            operation=OperationRef("shell.command", with_={"command": "printf executed"}),
                            gate={"all": ["step.ready_a.outputs.value", "step.ready_b.outputs.value"]},
                        ),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(result.outputs["can_execute"])
        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(result.outputs["gate_blockers"], ["mutate"])
        mutate = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "mutate")
        self.assertEqual(mutate["status"], "gate_blocked")
        failed = [item["expression"] for item in mutate["gate_report"]["failed"]]
        self.assertEqual(failed, ["step.ready_a.outputs.value", "step.ready_b.outputs.value"])

    def test_check_reports_runtime_derived_gate_failure_from_preflight_probe_outputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="story-to-ready-like",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-story", operation=OperationRef("gh.issue"), register="loaded_story"),
                        Step(name="task-refs", value='${step.loaded_story.outputs.body | markdown["Tasks"].list_items}', register="task_refs"),
                        Step(
                            name="set-ready",
                            operation=OperationRef("gh.issue.close"),
                            gate={
                                "all": [
                                    'is_present(step.loaded_story.outputs.body | markdown["Acceptance"])',
                                    'is_present(step.loaded_story.outputs.body | markdown["Acceptance"].list[0])',
                                    'is_present(step.loaded_story.outputs.body | markdown["Tasks"])',
                                    'is_present(step.loaded_story.outputs.body | markdown["Tasks"].list[1])',
                                ]
                            },
                        ),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"body": "# Title\n\n## Tasks\n- one"})
            return OperationResult(status="ok", outputs={})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(result.outputs["can_execute"])
        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(result.outputs["gate_blockers"], ["set-ready"])
        mutate = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "set-ready")
        self.assertEqual(mutate["status"], "gate_blocked")
        self.assertEqual(
            [item["expression"] for item in mutate["gate_report"]["failed"]],
            [
                'is_present(step.loaded_story.outputs.body | markdown["Acceptance"])',
                'is_present(step.loaded_story.outputs.body | markdown["Acceptance"].list[0])',
                'is_present(step.loaded_story.outputs.body | markdown["Tasks"].list[1])',
            ],
        )

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
        self.assertFalse(result.outputs["verdict_basis_stale"])
        self.assertIn("git.branch", result.outputs["used_probe_scopes"])
        self.assertIn("git.branch", result.outputs["stale_probe_scopes"])
        self.assertIn("git.branch", result.outputs["potential_probe_invalidation_scopes"])

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

        self.assertFalse(result.outputs["verdict_basis_stale"])
        self.assertIn("gh.issue", result.outputs["used_probe_scopes"])
        self.assertIn("gh.*", result.outputs["potential_probe_invalidation_scopes"])

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
            result.outputs["guard_details"][0]["probes"],
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

    def test_check_applies_profile_switch_from_prior_step_output(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repo_kind": {}},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="select-profile", value="frontend", register="selected"),
                        Step(name="switch-profile", profile_switch="${step.selected.outputs.value}"),
                    )
                ),
                GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
            ),
        )
        profiles = {"frontend": Profile(name="frontend", inputs={"repo_kind": "frontend"})}

        result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(result.outputs["preflight_registers"]["selected"]["outputs"]["value"], "frontend")
        self.assertEqual(result.outputs["preflight_step_items"][0]["status"], "interpreted")
        self.assertEqual(result.outputs["preflight_step_items"][1]["status"], "interpreted")

    def test_check_applies_workflow_declared_profile_before_guards(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            profile="frontend",
            declared_inputs={"repo_kind": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
                StepBlock(steps=(Step(name="remember", value="ok"),)),
            ),
        )
        profiles = {"frontend": Profile(name="frontend", inputs={"repo_kind": "frontend"})}

        result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])

    def test_check_rejects_missing_workflow_declared_profile_before_execution(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            profile="frontend",
            blocks=(StepBlock(steps=(Step(name="remember", value="ok"),)),),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "runtime.workflow.profile.not_available")

    def test_check_treats_publish_step_as_read_only_analyzable(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="select-profile", value="frontend", register="selected"),
                        Step(
                            name="publish-selected",
                            gate={"all": ["step.selected.outputs.value | is_string"]},
                            publish={"profile": "${step.selected.outputs.value}", "summary": "ready"},
                        ),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertEqual(result.outputs["preflight_step_items"][1]["preflight_classification"], "read_only_analyzable")
        self.assertEqual(result.outputs["preflight_step_items"][1]["status"], "interpreted")

    def test_check_surfaces_nested_probe_failure_root_cause_for_value_step(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  repository: owner/repo
  issue_number: 7
let:
  story_body: gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body
blocks:
  - steps:
      - name: Extract story task refs
        value: '${markdown["Tasks"].list_items with{root: story_body}}'
        register: task_refs
      - name: Publish selected story task
        uses: shell.command
        gate: is_present(step.task_refs.outputs.value)
        with:
          command: "echo hi"
"""
        )

        def probe(resolved_probe, _workflow):
            if resolved_probe.reference == "gh.issue":
                return OperationResult(
                    status="state_error",
                    summary="missing auth",
                    diagnostics=(
                        Diagnostic(
                            code="gh.auth_missing",
                            level="error",
                            message="GitHub auth missing",
                            path=(),
                            details={
                                "is_external": True,
                                "classification": "auth_failed",
                                "external_tool": "gh",
                                "external_system": "github",
                            },
                        ),
                    ),
                )
            return OperationResult(status="ok")

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["preflight_halts"][0]["step_name"], "Extract story task refs")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.call_probe_failed")
        self.assertIn("GitHub auth missing", result.diagnostics[0].message)
        self.assertIn("external github failure reported by gh", result.diagnostics[0].message)
        self.assertEqual(result.diagnostics[0].details["cause_code"], "gh.auth_missing")
        self.assertEqual(result.diagnostics[1].code, "gh.auth_missing")

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
                "steps:\n  - name: switch\n    profile_switch: \"frontend\"\n",
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

    def test_check_marks_frontier_allowed_when_effectful_step_is_reachable_and_no_later_guards_remain(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),
                        Step(name="ready", value=True, register="ready"),
                        Step(name="comment", operation=OperationRef("gh.issue.close"), gate="step.ready.outputs.value"),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            self.assertEqual(resolved_guard.reference, "gh.issue")
            return OperationResult(status="ok", outputs={"exists": True})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["analysis_complete"])
        self.assertTrue(result.outputs["can_execute"])
        self.assertEqual(result.outputs["frontier_ready_step"], "comment")
        self.assertEqual(result.outputs["preflight_halts"][0]["reason"], "effectful_step_encountered")
        self.assertEqual(result.outputs["allowed_basis"], "current_observed_state")

    def test_check_marks_frontier_allowed_after_expanded_preflight_when_final_gate_is_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "inspect.yml"
            fragment.write_text(
                "blocks:\n  - guards:\n      - 1 == 1\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="inspect.yml", resolved_run_path=str(fragment)),)),
                    StepBlock(
                        steps=(
                            Step(name="load", operation=OperationRef("gh.issue"), register="issue"),
                            Step(name="ready", value=True, register="ready"),
                            Step(name="comment", operation=OperationRef("gh.issue.close"), gate="step.ready.outputs.value"),
                        )
                    ),
                ),
            )

            def probe(resolved_guard, _workflow):
                if resolved_guard.reference == "gh.issue":
                    return OperationResult(status="ok", outputs={"exists": True})
                return OperationResult(status="ok")

            result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertTrue(result.outputs["can_execute"])
            self.assertTrue(result.outputs["analysis_complete"])
            self.assertEqual(result.outputs["frontier_ready_step"], "comment")
            self.assertEqual(result.outputs["allowed_basis"], "current_observed_state")

    def test_check_marks_frontier_allowed_after_context_application_when_final_gate_is_satisfied(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="switch", profile_switch="frontend"),)),
                StepBlock(
                    steps=(
                        Step(name="ready", value=True, register="ready"),
                        Step(name="comment", operation=OperationRef("gh.issue.close"), gate="step.ready.outputs.value"),
                    )
                ),
            ),
        )
        profiles = {"frontend": Profile(name="frontend")}

        result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertTrue(result.outputs["can_execute"])
        self.assertEqual(result.outputs["frontier_ready_step"], "comment")
        self.assertEqual(result.outputs["allowed_basis"], "current_observed_state")

    def test_check_surfaces_nested_gate_blockers_from_fan_out_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "validate.yml"
            fragment.write_text(
                textwrap.dedent(
                    """
                    args:
                      item: string
                    blocks:
                      - steps:
                          - name: load
                            uses: gh.project.issue
                            register: linked
                            with:
                              repository: "owner/repo"
                              issue_number: 1
                              project_id: ${inputs.project_id}
                          - name: gate-task
                            gate:
                              all:
                                - step.linked.outputs.exists
                                - step.linked.outputs.status | eq("Ready")
                            result:
                              item: args.item
                    """
                ),
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="root",
                inputs={"items": ["owner/repo#1", "owner/repo#2"], "project_id": "PVT_demo"},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="validate.yml", resolved_run_path=str(fragment), for_each="${inputs.items}", run_with={"item": "${item}"}),
                        )
                    ),
                ),
            )

            def probe(resolved_guard, _workflow):
                self.assertEqual(resolved_guard.reference, "gh.project.issue")
                return OperationResult(status="ok", outputs={"exists": True, "type": "Task", "status": "Backlog"})

            result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(result.outputs["gate_blockers"], ["expand"])
        nested = result.outputs["nested_gate_blockers"]
        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0]["expanded_item"], "owner/repo#1")
        self.assertEqual(nested[0]["gate_reports"][0]["verdict"], "failed")

    def test_check_surfaces_nested_gate_blockers_from_inline_fan_out(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="root",
            inputs={"items": ["owner/repo#1", "owner/repo#2"], "project_id": "PVT_demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(
                                Step(
                                    name="load",
                                    operation=OperationRef(
                                        "gh.project.issue",
                                        with_={
                                            "repository": 'item | text.before("#")',
                                            "issue_number": 'item | text.after("#")',
                                            "project_id": "inputs.project_id",
                                        },
                                    ),
                                    register="linked",
                            ),
                                Step(
                                    name="gate-task",
                                    gate={
                                        "all": [
                                            "step.linked.outputs.exists",
                                            'step.linked.outputs.status | eq("Ready")',
                                        ]
                                    },
                                ),
                            ),
                            register="runs",
                        ),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            self.assertEqual(resolved_guard.reference, "gh.project.issue")
            return OperationResult(status="ok", outputs={"exists": True, "type": "Task", "status": "Backlog"})

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(result.outputs["gate_blockers"], ["expand"])
        nested = result.outputs["nested_gate_blockers"]
        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0]["expanded_item"], "owner/repo#1")
        self.assertEqual(nested[0]["gate_reports"][0]["failed"][0]["expression"], 'step.linked.outputs.status | eq("Ready")')
        self.assertNotIn("visible_registers", nested[0]["gate_reports"][0])

    def test_check_supports_standalone_gate_checkpoint_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="prepare", value=True, register="ready"),
                        Step(name="checkpoint", gate="step.ready.outputs.value"),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")

    def test_check_gate_report_includes_on_fail_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            inputs={"repository": "owner/repo", "issue_number": 1},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="profile", value="mobile", register="profile"),
                        Step(name="linked", value={"exists": True, "status": "Backlog"}, register="linked_project_issue"),
                        Step(
                            name="checkpoint",
                            gate={
                                "all": [
                                    "step.linked_project_issue.outputs.value.exists",
                                    'step.linked_project_issue.outputs.value.status | eq("Ready")',
                                ]
                            },
                            gate_on_fail={
                                "profile": "${step.profile.outputs.value}",
                                "issue_number": "${inputs.issue_number}",
                                "repository": "${inputs.repository}",
                                "status": "${step.linked_project_issue.outputs.value.status}",
                            },
                        ),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(
            result.outputs["preflight_step_items"][2]["gate_report"]["on_fail_context"],
            {
                "profile": "mobile",
                "issue_number": 1,
                "repository": "owner/repo",
                "status": "Backlog",
            },
        )
        checkpoint = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "checkpoint")
        self.assertEqual(checkpoint["status"], "gate_blocked")
        self.assertEqual(checkpoint["gate_status"], "failed")

    def test_check_evaluates_item_root_inside_inline_gate(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="fan-out-check",
            inputs={"items": ["ok", "bad"]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(
                                Step(name="gate-item", gate='item == "ok"'),
                            ),
                        ),
                    )
                ),
            ),
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "blocked")
        self.assertEqual(result.outputs["gate_blockers"], ["expand"])
        nested = result.outputs["nested_gate_blockers"][0]
        self.assertEqual(nested["expanded_item"], "bad")
        self.assertEqual(nested["gate_reports"][0]["failed_causes"][0]["rendered"], 'item == "ok"')

    def test_check_marks_inline_profile_switch_fan_out_as_interpreted_context_logic(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: profile-switch-inline-probe
inputs:
  profiles: []
blocks:
  - guards:
      - git.repo.exists
  - steps:
      - name: Validate profiles inline
        for_each: inputs.profiles
        steps:
          - name: Switch runtime profile inline
            profile_switch: ${item}
'''
        )
        workflow = replace(workflow, inputs={"profiles": ["mobile"]})
        profiles = {"mobile": Profile(name="mobile")}

        result = check_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        item = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "Validate profiles inline")
        self.assertEqual(item["status"], "interpreted")
        self.assertEqual(item["preflight_classification"], "context_only")
        self.assertEqual(item["expanded_item"], "mobile")

    def test_check_evaluates_git_probe_references_inside_nested_inline_gate(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: workspace-hygiene-inline
inputs:
  profiles: []
blocks:
  - guards:
      - git.repo.exists
  - steps:
      - name: Validate workspace profile hygiene
        for_each: inputs.profiles
        steps:
          - name: Switch runtime profile inline
            profile_switch: ${item}
          - name: Gate workspace profile hygiene
            gate:
              all:
                - git.branch.value == "main"
                - git.worktree.clean
'''
        )
        workflow = replace(workflow, inputs={"profiles": ["mobile"]})
        profiles = {"mobile": Profile(name="mobile")}

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.repo":
                return OperationResult(status="ok", outputs={"exists": True})
            if resolved_guard.reference == "git.branch":
                return OperationResult(status="ok", outputs={"value": "main"})
            if resolved_guard.reference == "git.worktree":
                return OperationResult(status="ok", outputs={"clean": True})
            return OperationResult(status="state_error", summary="unexpected probe")

        result = check_workflow(workflow, available_profiles=profiles, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["allowed_state"], "allowed")
        self.assertEqual(result.outputs["incomplete_reasons"], [])
        nested = next(item for item in result.outputs["preflight_step_items"] if item["name"] == "Validate workspace profile hygiene")
        self.assertEqual(nested["status"], "interpreted")
        self.assertEqual(nested["expanded_item"], "mobile")

    def test_check_reports_strong_preflight_support_when_recommended_probes_match_exactly(self) -> None:
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
        self.assertEqual(len(support["matched_probes"]), 3)
        self.assertEqual(support["unmaterialized_probes"], [])
        self.assertEqual(support["missing_probes"], [])

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
        self.assertEqual(len(support["matched_probes"]), 2)
        self.assertEqual(support["unmaterialized_probes"], [])
        self.assertEqual(
            support["missing_probes"],
            [
                {
                    "probe": "git.range",
                    "with": {"base": "@{upstream}", "head": {"expression": "step.branch_name.outputs.value"}},
                    "fields": [],
                }
            ],
        )

    def test_check_matches_guard_probe_references_with_action_probe_placeholders(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="task-to-ready",
            inputs={"repository": "acme/repo", "project_id": "PVT_demo", "issue_number": 7},
            let_bindings={
                "project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)",
                "status_field": 'gh.project.field(project_id=inputs.project_id, field="Status")',
                "ready_option": 'gh.project.field.option(project_id=inputs.project_id, field="Status", option="Ready")',
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="project_issue.exists"),
                        Guard(expr="status_field.exists"),
                        Guard(expr="ready_option.exists"),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "inputs.repository",
                                    "issue_number": "inputs.issue_number",
                                    "project_id": "inputs.project_id",
                                    "field": "Status",
                                    "option": "Ready",
                                },
                            ),
                        ),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            outputs = {
                "gh.project.issue": {"exists": True},
                "gh.project.field": {"exists": True},
                "gh.project.field.option": {"exists": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][0]["preflight_support"]
        self.assertEqual(support["strength"], "strong")
        self.assertEqual(support["unmaterialized_probes"], [])
        self.assertEqual(support["missing_probes"], [])

    def test_check_marks_authored_probe_intent_as_unmaterialized_when_not_successfully_observed(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="close-story",
            declared_inputs={"repository": {}, "issue_number": {}, "project_id": {}},
            let_bindings={
                "story_project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)",
                "status_field": 'gh.project.field(project_id=inputs.project_id, field="Status")',
                "done_option": 'gh.project.field.option(project_id=inputs.project_id, field="Status", option="Done")',
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="story_project_issue.exists"),
                        Guard(expr="status_field.exists"),
                        Guard(expr="done_option.exists"),
                    )
                ),
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
                                    "option": "Done",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.project.issue":
                return OperationResult(status="probe_failed", diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),))
            outputs = {
                "gh.project.field": {"exists": True},
                "gh.project.field.option": {"exists": True},
            }
            return OperationResult(status="ok", outputs=outputs[resolved_guard.reference])

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support = result.outputs["preflight_step_items"][0]["preflight_support"]
        self.assertEqual(support["strength"], "partial")
        self.assertEqual(len(support["matched_probes"]), 2)
        self.assertEqual(support["missing_probes"], [])
        self.assertEqual(support["unmaterialized_probes"][0]["probe"], "gh.project.issue")

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
            result.outputs["preflight_step_items"][0]["probes"],
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
        self.assertEqual(support["matched_probes"], [])
        self.assertEqual(
            support["missing_probes"],
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
            support["missing_probes"],
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

    def test_check_recommends_missing_probes_for_guardless_effectful_block(self) -> None:
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
            support["missing_probes"],
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
            workflow_profile_declared=None,
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
            analysis.preflight_step_items[1]["preflight_support"]["missing_probes"],
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
            workflow_profile_declared=None,
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
            workflow_profile_declared=None,
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
            workflow_profile_declared=None,
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
