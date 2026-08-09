import unittest
import tempfile
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import execute_workflow, explain_execution_result, explain_runtime_result, explain_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExplainModeTest(unittest.TestCase):
    def test_explain_reports_guard_block_reason_and_next_action(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='git.branch.value != "main"'),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.branch":
                return OperationResult(status="ok", outputs={"value": "main"})
            return OperationResult(status="ok")

        result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["reason_category"], "guard")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "resolve_blocking_guards")
        self.assertEqual(result.outputs["explanation"]["guard_details"][0]["failed_subcondition"], 'git.branch.value != "main"')

    def test_explain_reports_resolution_problem(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "resolution")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "fix_operation_references")

    def test_explain_reports_undeclared_root_input_inside_run_target_as_validation_problem(self) -> None:
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

            result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
            self.assertEqual(result.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")
            self.assertEqual(result.outputs["explanation"]["category"], "validation")

    def test_explain_reports_ok_state_and_safe_next_action(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)

    def test_explain_preserves_shared_analysis_tree_from_plan(self) -> None:
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
                            operation=OperationRef("git.range", with_={"base": "@{upstream}", "head": "${step.branch_name.outputs.value}"}),
                            register="range",
                        ),
                        Step(name="push", operation=OperationRef("git.sync.push", with_={"branch": "${step.branch_name.outputs.value}"})),
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

        explained = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertIsNotNone(explained.analysis_tree)
        self.assertEqual(explained.outputs["explanation"]["preflight_support_steps"][0]["name"], explained.analysis_tree.preflight_step_items[4]["name"])
        self.assertEqual(explained.outputs["explanation"]["category"], "incomplete")
        self.assertEqual(explained.outputs["next_actions"][0]["action"], "complete_preflight_analysis")

    def test_explain_reports_incomplete_preflight_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="prepare", operation=OperationRef("gh.issue")),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["explanation"]["category"], "preflight_step")
        self.assertEqual(result.outputs["explanation"]["blockers"], ["prepare"])
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_read_only_observation")

    def test_explain_surfaces_preflight_halts_for_incomplete_analysis(self) -> None:
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
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["explanation"]["preflight_halts"][0]["reason"], "effectful_step_encountered")
        self.assertEqual(result.outputs["preflight_step_items"][1]["condition_status"], "true")

    def test_explain_reports_partial_preflight_support_with_rendered_recommendations(self) -> None:
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
                            operation=OperationRef("git.range", with_={"base": "@{upstream}", "head": "${inputs.branch}"}),
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

        result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        support_step = result.outputs["explanation"]["preflight_support_steps"][0]
        self.assertEqual(support_step["name"], "push")
        self.assertEqual(support_step["preflight_support"]["strength"], "partial")
        self.assertEqual(
            support_step["preflight_support"]["missing_probes"],
            [
                {
                    "probe": "git.range",
                    "with": {"base": "@{upstream}", "head": {"expression": "step.branch_name.outputs.value"}},
                    "fields": [],
                }
            ],
        )

    def test_explain_execution_result_reports_gate_block(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            steps=(
                Step(name="ready", value=False, register="ready"),
                Step(
                    name="mutate",
                    operation=OperationRef("shell.command", with_={"command": "printf executed"}),
                    gate="step.ready.outputs.value",
                ),
            ),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "gate")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "satisfy_step_gate")
        self.assertEqual(result.outputs["explanation"]["blockers"], ["mutate"])

    def test_explain_reports_runtime_derived_gate_block_from_preflight_knowledge(self) -> None:
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

        result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["explanation"]["category"], "gate")
        self.assertEqual(result.outputs["explanation"]["blockers"], ["set-ready"])
        gate_detail = result.outputs["explanation"]["step_gate_details"][0]
        self.assertEqual(gate_detail["verdict"], "failed")

    def test_explain_reports_read_only_preflight_failure_clearly(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "unknown",
                    "analysis_complete": False,
                    "incomplete_reasons": ["read_only_step_failed"],
                    "preflight_halts": [
                        {
                            "reason": "read_only_step_failed",
                            "step_name": "Load story task item details in batch",
                            "details": {"status": "invalid_content_ref"},
                        }
                    ],
                },
            )
        )

        self.assertEqual(result.outputs["explanation"]["category"], "preflight_step")
        self.assertEqual(result.outputs["explanation"]["blockers"], ["Load story task item details in batch"])

    def test_explain_reports_unanalyzable_preflight_step_clearly(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "unknown",
                    "analysis_complete": False,
                    "incomplete_reasons": ["preflight_step_not_analyzable"],
                    "preflight_halts": [
                        {
                            "reason": "preflight_step_not_analyzable",
                            "step_name": "Validate linked task readiness",
                            "details": {
                                "classification": "read_only_unanalyzable",
                                "reference": "fragments/validate-story-task-readiness.yml",
                            },
                        }
                    ],
                },
            )
        )

        self.assertEqual(result.outputs["explanation"]["category"], "preflight_step")
        self.assertEqual(result.outputs["explanation"]["blockers"], ["Validate linked task readiness"])
        self.assertIn("nested gate results", result.outputs["explanation"]["why"])
        self.assertEqual(result.outputs["next_actions"][0]["action"], "analyze_unanalyzable_preflight_step")

    def test_explain_reports_nested_gate_blockers_from_fan_out(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "blocked",
                    "analysis_complete": True,
                    "gate_blockers": ["Validate linked task readiness"],
                    "nested_gate_blockers": [
                        {
                            "expanded_from_step": "Validate linked task readiness",
                            "expanded_item_index": 0,
                            "expanded_item": "kergma-lw/checklist-mobile#1",
                            "gate_blockers": ["Gate linked task readiness"],
                            "gate_reports": [
                                {
                                    "field": "gate",
                                    "verdict": "failed",
                                    "failed": [
                                        {"expression": 'step.linked_project_issue.outputs.status | eq("Ready")', "verdict": "failed"}
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
        )

        self.assertEqual(result.outputs["explanation"]["category"], "gate")
        self.assertIn("fan-out", result.outputs["explanation"]["why"])
        nested = result.outputs["explanation"]["nested_gate_blockers"][0]
        self.assertEqual(nested["expanded_item"], "kergma-lw/checklist-mobile#1")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "satisfy_nested_step_gate")

    def test_explain_summary_for_inline_fan_out_nested_gate(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "blocked",
                    "analysis_complete": True,
                    "gate_blockers": ["Validate linked task readiness"],
                    "nested_gate_blockers": [
                        {
                            "expanded_from_step": "Validate linked task readiness",
                            "expanded_item_index": 0,
                            "expanded_item": "kergma-lw/checklist-mobile#1",
                            "gate_blockers": ["Gate linked task readiness"],
                            "gate_reports": [
                                {
                                    "failed": [
                                        {"expression": 'step.linked_project_issue.outputs.status | eq("Ready")'}
                                    ]
                                }
                            ],
                        }
                    ],
                },
            )
        )

        self.assertEqual(result.outputs["explanation"]["category"], "gate")
        self.assertIn("kergma-lw/checklist-mobile#1", result.outputs["explanation"]["why"])
        self.assertIn('step.linked_project_issue.outputs.status | eq("Ready")', result.outputs["explanation"]["why"])

    def test_explain_uses_structural_failed_cause_for_any_group(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "blocked",
                    "analysis_complete": True,
                    "gate_blockers": ["Validate linked task readiness"],
                    "nested_gate_blockers": [
                        {
                            "expanded_from_step": "Validate linked task readiness",
                            "expanded_item": "kergma-lw/checklist-mobile#1",
                            "gate_reports": [
                                {
                                    "failed": [
                                        {"expression": 'step.linked_project_issue.outputs.type | eq("Task")', "rendered": 'step.linked_project_issue.outputs.type | eq("Task")'},
                                        {"expression": 'step.linked_project_issue.outputs.type | eq("Bug")', "rendered": 'step.linked_project_issue.outputs.type | eq("Bug")'},
                                    ],
                                    "failed_causes": [
                                        {
                                            "kind": "any",
                                            "verdict": "failed",
                                            "path": ["all", "1"],
                                            "rendered": 'any(step.linked_project_issue.outputs.type | eq("Task"), step.linked_project_issue.outputs.type | eq("Bug"))',
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
        )

        self.assertIn(
            'any(step.linked_project_issue.outputs.type | eq("Task"), step.linked_project_issue.outputs.type | eq("Bug"))',
            result.outputs["explanation"]["why"],
        )

    def test_explain_reports_frontier_ready_step_when_preflight_reaches_effectful_step(self) -> None:
        result = explain_runtime_result(
            RuntimeResult(
                mode=Mode.CHECK,
                status=RuntimeStatus.OK,
                diagnostics=(),
                outputs={
                    "allowed_state": "allowed",
                    "analysis_complete": True,
                    "frontier_ready_step": "Set story status to Ready",
                },
            )
        )

        self.assertEqual(result.outputs["explanation"]["category"], "ok")
        self.assertIn("Set story status to Ready", result.outputs["explanation"]["why"])
        self.assertIn("current observed inputs and state", result.outputs["explanation"]["why"])

    def test_explain_keeps_preflight_support_consistent_with_plan(self) -> None:
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

        explain_result = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(explain_result.outputs["step_items"][4]["preflight_support"]["strength"], "strong")
        self.assertEqual(explain_result.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["strength"], "strong")

    def test_explain_surfaces_structural_recommendations_when_inputs_are_missing(self) -> None:
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

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["explanation"]["category"], "preflight_step")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_read_only_observation")
        self.assertEqual(result.outputs["explanation"]["preflight_support_steps"][0]["name"], "push")
        self.assertEqual(result.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["strength"], "weak")
        self.assertEqual(
            result.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["missing_probes"][2],
            {
                "probe": "git.range",
                "with": {"base": "@{upstream}", "head": {"expression": "step.branch_name.outputs.value"}},
                "fields": [],
            },
        )

    def test_explain_surfaces_structural_recommendations_for_guardless_effectful_block(self) -> None:
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

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["explanation"]["category"], "ok")
        self.assertEqual(result.outputs["explanation"]["preflight_support_steps"][0]["name"], "set-status")
        self.assertEqual(
            result.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["missing_probes"][2],
            {
                "probe": "gh.project.field.option",
                "with": {"project_id": {"expression": "inputs.project_id"}, "field": "Status", "option": "In review"},
                "fields": ["exists"],
            },
        )
        self.assertEqual(
            result.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["missing_probes"][1],
            {
                "probe": "gh.project.field",
                "with": {"project_id": {"expression": "inputs.project_id"}, "field": "Status"},
                "fields": ["exists"],
            },
        )

    def test_explain_preserves_expanded_run_reasoning(self) -> None:
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

            result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.outputs["explanation"]["category"], "ok")
            expanded = [item for item in result.outputs["block_items"] if item.get("expanded_from_run") == "profile-guard.yml"]
            self.assertEqual(len(expanded), 1)

    def test_explain_runtime_result_covers_execution_failure(self) -> None:
        execution_result = RuntimeResult(
            mode="execute",  # type: ignore[arg-type]
            status=RuntimeStatus.EXECUTION_ERROR,
            failed_step="ship",
            outputs={"executed_steps": [], "skipped_steps": ["close"]},
        )

        result = explain_runtime_result(execution_result)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["explanation"]["category"], "execution")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_failed_step")

    def test_explain_reports_bootstrap_problem_separately_from_guard_logic(self) -> None:
        runtime_result = RuntimeResult(
            mode="check",  # type: ignore[arg-type]
            status=RuntimeStatus.GUARD_FAILED,
            outputs={
                "blockers": ["git.branch"],
                "guard_details": [{"reference": "git.branch", "failure_kind": "not_repository"}],
                "bootstrap_details": [{"namespace": "git", "status": "not_repository", "context": {}}],
            },
        )

        result = explain_runtime_result(runtime_result)

        self.assertEqual(result.outputs["explanation"]["category"], "bootstrap")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "repair_connector_bootstrap")

    def test_explain_execution_result_wraps_execute_mode(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(), steps=(Step(name="ship", operation=OperationRef("shell.command")),))

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode.value, "explain")
        self.assertIn("explanation", result.outputs)

    def test_explain_execution_result_preserves_step_condition_outcomes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            guards=(),
            steps=(Step(name="ship", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_condition_details"][0]["outcome"], "skipped")
        self.assertEqual(result.outputs["step_condition_details"][0]["reason"], "condition_false")

    def test_explain_execution_result_preserves_adapter_failure_diagnostics(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"body": "## Notes\n- ship\n"},
            steps=(
                Step(
                    name="select",
                    value='${markdown["Tasks"].list with{root: inputs.body}}',
                    register="picked",
                ),
            ),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["reason_category"], "execution")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_not_found")

    def test_explain_execution_result_preserves_text_adapter_failure_diagnostics(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"body": "hello\nworld"},
            steps=(
                Step(
                    name="select",
                    value='${text.lines.after("h") with{root: inputs.body}}',
                    register="picked",
                ),
            ),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["reason_category"], "execution")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_invalid_path")

    def test_explain_execution_result_preserves_json_adapter_ambiguous_match_diagnostics(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"body": '{"items":[{"id":2},{"id":2}]}'},
            steps=(
                Step(
                    name="select",
                    value='${json.items.one(id=2) with{root: inputs.body}}',
                    register="picked",
                ),
            ),
        )

        result = explain_execution_result(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["reason_category"], "execution")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_ambiguous_match")

    def test_explain_surfaces_runtime_only_fan_out_in_incomplete_mode(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            steps=(
                Step(name="load-items", operation=OperationRef("gh.issue"), register="items"),
                Step(name="inspect", run="fragment.yml", for_each="${step.items.outputs.items}", register="runs"),
            ),
        )

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["explanation"]["category"], "ok")
        self.assertEqual(result.outputs["explanation"]["fan_out_items"][0]["fan_out"]["source_status"], "runtime_only")

    def test_explain_surfaces_inline_fan_out_body_kind(self) -> None:
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

        result = explain_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["explanation"]["fan_out_items"][0]["body_kind"], "inline_repeated_steps")

    def test_explain_surfaces_fan_out_failure_details(self) -> None:
        execution_result = RuntimeResult(
            mode="execute",  # type: ignore[arg-type]
            status=RuntimeStatus.EXECUTION_ERROR,
            failed_step="nested-result",
            outputs={"fan_out_failure": {"step": "expand", "item_index": 1, "item_count": 2}},
        )

        result = explain_runtime_result(execution_result)

        self.assertEqual(result.outputs["explanation"]["fan_out_failure"]["item_index"], 1)
        self.assertEqual(result.outputs["explanation"]["why"], "Execution started but a fan-out item failed")


if __name__ == "__main__":
    unittest.main()
