import unittest
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch

from ordo.model.diagnostic import Diagnostic
from ordo.model.connector import Connector, ConnectorRegistry
from ordo.model.launcher import Launcher
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.playbook import activate_playbook
from ordo.runtime import execute_workflow, load_workflow_text, plan_workflow
from ordo.runtime.loading import load_workflow_file
from ordo.runtime.executing import (
    _append_execution_error_block_item,
    _append_execution_ok_block_item,
    _initialize_execute_context,
    _is_execute_probe_step,
    _is_execute_profile_switch_builtin,
    _is_execute_profile_switch_operation,
    _is_execute_run_step,
    _prepare_tree_driven_step_context,
    _record_step_runtime_result,
)
from ordo.runtime.providers import ConnectorProvider
from ordo.runtime.resolution import ResolvedBuiltinStep, ResolvedOperation, ResolvedRunStep
from ordo.model.connector import OperationContract

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExecuteModeTest(unittest.TestCase):
    @staticmethod
    def _completed(*, returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_prepare_tree_driven_step_context_marks_reusable_value_step(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", steps=(Step(name="flag", value=True, register="flag"),))
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        context = _prepare_tree_driven_step_context(
            step=workflow.steps[0],
            workflow=workflow,
            execution_tree=plan_result.outputs["execution_tree"],
            preflight_reuse={"flag": {"register": "flag", "step_result": {"status": "ok", "summary": "derived", "outputs": {"value": True}}}},
            block_index=0,
            step_index=0,
        )

        self.assertEqual(context["should_execute"], True)
        self.assertIsNotNone(context["reused_preflight"])
        self.assertEqual(context["condition_source"], "runtime")

    def test_prepare_tree_driven_step_context_uses_tree_state_for_conditions(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                StepBlock(steps=(Step(name="ship", operation=OperationRef("shell.command"), if_="${step.flag.outputs.value}"),)),
            ),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        workflow.step_results["flag"] = {"status": "ok", "summary": "derived", "outputs": {"value": True}}

        context = _prepare_tree_driven_step_context(
            step=workflow.blocks[1].steps[0],
            workflow=workflow,
            execution_tree=plan_result.outputs["execution_tree"],
            preflight_reuse={},
            block_index=1,
            step_index=0,
        )

        self.assertEqual(context["should_execute"], True)
        self.assertEqual(context["condition_source"], "execution_tree_state")

    def test_execute_reports_undeclared_root_input_inside_run_target_as_validation_error(self) -> None:
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

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
            self.assertEqual(result.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")

    def test_execute_reports_non_boolean_guard_result_as_guard_error(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"title": "demo"}, guards=(Guard(expr="inputs.title"),), steps=())

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.operation_results[0].status, "execution_error")
        self.assertEqual(result.operation_results[0].diagnostics[-1].code, "runtime.guard.result_type")
        self.assertEqual(result.outputs["guard_details"][0]["failure_kind"], "result_type")
        self.assertEqual(result.failed_guard, "inputs.title")

    def test_execute_guard_details_include_affected_inputs_and_lets(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: story-tasks-show
inputs:
  repository: owner/repo
  issue_number: 103
  project_id: demo-project
let:
  story_project_issue: gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)
blocks:
  - guards:
      - story_project_issue.exists
  - steps: []
"""
        )

        def probe(_resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"exists": False})

        result = execute_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["guard_details"][0]["affected_lets"], ["story_project_issue"])
        self.assertEqual(
            result.outputs["guard_details"][0]["affected_inputs"],
            ["inputs.repository", "inputs.issue_number", "inputs.project_id"],
        )

    def test_execute_failure_result_keeps_step_detail_with_resolved_inputs(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: story-tasks-show
inputs:
  content_refs:
    - owner/repo#1
blocks:
  - guards: []
  - steps:
      - name: Load story task item details in batch
        uses: gh.project.items
        with:
          content_refs: ${inputs.content_refs}
"""
        )

        def step_executor(resolved_step, _workflow):
            self.assertEqual(resolved_step.resolved_inputs, {"content_refs": ["owner/repo#1"]})
            return OperationResult(
                status="execution_error",
                summary="GitHub project item content_refs must be a list of OWNER/REPO#NUMBER strings",
            )

        result = execute_workflow(workflow, step_executor=step_executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "Load story task item details in batch")
        self.assertEqual(result.operation_results[0].raw["step_detail"]["step"], "Load story task item details in batch")
        self.assertEqual(result.operation_results[0].raw["step_detail"]["reference"], "gh.project.items")
        self.assertEqual(result.operation_results[0].raw["step_detail"]["resolved_inputs"], {"content_refs": ["owner/repo#1"]})

    def test_record_step_runtime_result_updates_registers_and_diagnostics(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", steps=(Step(name="flag", value=True, register="flag"),))
        step = workflow.steps[0]
        diagnostic = Diagnostic(code="runtime.test", level="info", message="ok")
        result = OperationResult(status="ok", summary="derived", outputs={"value": True}, diagnostics=(diagnostic,))
        operation_results: list[OperationResult] = []
        diagnostics: list[Diagnostic] = []

        _record_step_runtime_result(
            workflow=workflow,
            step=step,
            result=result,
            operation_results=operation_results,
            diagnostics=diagnostics,
        )

        self.assertEqual(workflow.step_results["flag"]["outputs"]["value"], True)
        self.assertEqual(operation_results, [result])
        self.assertEqual(diagnostics, [diagnostic])

    def test_execute_accumulates_results_from_multiple_result_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"issue_number": 7},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="result-one", result={"summary": "first", "issue": "${inputs.issue_number}"}),
                        Step(name="result-two", result={"summary": "second"}),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [{"summary": "first", "issue": 7}, {"summary": "second"}])
        self.assertEqual(list(result.published), [])

    def test_execute_accumulates_published_from_multiple_publish_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="publish-one", publish={"summary": "first"}),
                        Step(name="publish-two", publish={"summary": "second"}),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [])
        self.assertEqual(list(result.published), [{"summary": "first"}, {"summary": "second"}])

    def test_execute_publish_allows_probe_reference_in_value_surface(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: publish
blocks:
  - steps:
      - name: publish-branch
        publish:
          branch: git.branch.value
          detached: git.branch.detached
"""
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.published), [{"branch": "feature/demo", "detached": False}])

    def test_execute_value_step_allows_probe_reference_in_value_surface(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: publish
blocks:
  - steps:
      - name: branch
        value: git.branch.value
        register: current_branch
"""
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(workflow.step_results["current_branch"]["outputs"]["value"], "feature/demo")

    def test_execute_result_allows_probe_reference_in_value_surface(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: publish
blocks:
  - steps:
      - name: branch-result
        result:
          branch: git.branch.value
"""
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [{"branch": "feature/demo"}])

    def test_execute_returns_empty_results_when_no_result_step_runs(self) -> None:
        workflow = Workflow(version=0, workflow="publish", steps=(Step(name="remember", value="ok"),))

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [])

    def test_execute_keeps_nested_results_local_to_nested_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: \"nested\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", resolved_run_path=str(fragment)),
                            Step(name="publish-parent", result={"summary": "parent"}),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [{"summary": "parent"}])

    def test_execute_emits_named_fallback_results_for_nested_run_without_explicit_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-value\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", register="nested_run", resolved_run_path=str(fragment)),
                            Step(name="remember", value="done"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [])
            self.assertEqual(workflow.step_results["nested_run"], {"results": [{"summary": 'Run-invoked workflow "nested" completed without explicit result.', "workflow": "nested"}]})

    def test_execute_registers_results_from_run_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: \"nested\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", register="nested_run", resolved_run_path=str(fragment)),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [[{"summary": "nested"}]])

    def test_execute_fans_out_run_results_over_array_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "args:\n  item: string\nversion: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                inputs={"items": ["one", "two"]},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", for_each="${inputs.items}", register="nested_run", resolved_run_path=str(fragment)),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(
                list(result.results),
                [[{"results": [{"summary": "one"}]}, {"results": [{"summary": "two"}]}]],
            )

    def test_execute_inline_fan_out_uses_item_scope_and_iteration_local_registers(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": ["one", "two"]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(
                                Step(name="capture", value="${item}", register="current_item"),
                                Step(name="emit", result={"summary": "${step.current_item.outputs.value}"}),
                            ),
                            register="runs",
                        ),
                        Step(name="copy", result="${step.runs.results}"),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(
            list(result.results),
            [[{"results": [{"summary": "one"}]}, {"results": [{"summary": "two"}]}]],
        )

    def test_execute_outer_if_false_skips_whole_inline_fan_out_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": ["one"], "enabled": False},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(Step(name="capture", value="${item}", register="current_item"),),
                            if_="inputs.enabled",
                            register="runs",
                        ),
                        Step(name="done", result={"summary": "ok"}),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertNotIn("expand", result.outputs["executed_steps"])
        self.assertIn("expand", result.outputs["skipped_steps"])
        self.assertEqual(list(result.results), [{"summary": "ok"}])

    def test_execute_inline_fan_out_inner_if_applies_per_iteration(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": [False, True]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(
                                Step(name="capture", value="${item}", register="current_item"),
                                Step(name="emit", result={"summary": "${step.current_item.outputs.value}"}, if_="step.current_item.outputs.value"),
                            ),
                            register="runs",
                        ),
                        Step(name="copy", result="${step.runs.results}"),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results)[0][1], {"results": [{"summary": True}]})
        self.assertEqual(list(result.results)[0][0]["results"][0]["workflow"], "publish::expand")

    def test_execute_can_use_gh_project_items_let_binding_for_guard_fan_out_and_publish(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={
                "project_id": "PVT_demo",
                "filters": [{"field": "Status", "value": "Ready"}],
            },
            let_bindings={
                "ready_items": "gh.project.items(project_id=inputs.project_id, filters=inputs.filters)",
            },
            blocks=(
                GuardBlock(guards=(Guard(expr="ready_items.count != 0"),)),
                StepBlock(
                    steps=(
                        Step(name="load-items", operation=OperationRef("gh.project.items", with_={"project_id": "${inputs.project_id}", "filters": "${inputs.filters}"}), register="loaded_items"),
                        Step(name="copy", result="${step.loaded_items.outputs.items}"),
                        Step(name="publish-count", publish={"summary": "matched", "count": "${step.loaded_items.outputs.count}"}),
                    )
                ),
            ),
        )

        items_payload = '{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_1","content":{"__typename":"Issue","number":7,"title":"First ready item","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready","field":{"id":"F_status","name":"Status"}}]}},{"id":"PVTI_2","content":{"__typename":"Issue","number":8,"title":"Second ready item","url":"https://github.com/owner/repo/issues/8","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready","field":{"id":"F_status","name":"Status"}}]}}]}}}}'
        fields_payload = '{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status","name":"Status","options":[{"id":"O_ready","name":"Ready"}]}]}}}}'

        def run_side_effect(argv, **kwargs):
            if argv[:3] == ["gh", "auth", "status"]:
                return self._completed(returncode=0, stdout="authenticated\n")
            command_text = " ".join(argv)
            if "items(first:100" in command_text:
                return self._completed(returncode=0, stdout=items_payload)
            if "fields(first:100" in command_text:
                return self._completed(returncode=0, stdout=fields_payload)
            raise AssertionError(f"Unexpected command: {argv!r}")

        with patch("subprocess.run", side_effect=run_side_effect):
            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(
            list(result.results),
            [[
                {
                    "item_id": "PVTI_1",
                    "content_kind": "Issue",
                    "repository": "owner/repo",
                    "number": 7,
                    "title": "First ready item",
                    "url": "https://github.com/owner/repo/issues/7",
                },
                {
                    "item_id": "PVTI_2",
                    "content_kind": "Issue",
                    "repository": "owner/repo",
                    "number": 8,
                    "title": "Second ready item",
                    "url": "https://github.com/owner/repo/issues/8",
                },
            ]],
        )
        self.assertEqual(list(result.published), [{"summary": "matched", "count": 2}])

    def test_execute_publish_can_consume_probe_backed_let_binding(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={
                "project_id": "PVT_demo",
                "filters": [{"field": "Status", "value": "Ready"}],
            },
            let_bindings={
                "ready_count": "gh.project.items(project_id=inputs.project_id, filters=inputs.filters).count",
            },
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="publish-count", publish={"summary": "matched", "count": "${ready_count}"}),
                    )
                ),
            ),
        )

        items_payload = '{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_1","content":{"__typename":"Issue","number":7,"title":"First ready item","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready","field":{"id":"F_status","name":"Status"}}]}},{"id":"PVTI_2","content":{"__typename":"Issue","number":8,"title":"Second ready item","url":"https://github.com/owner/repo/issues/8","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready","field":{"id":"F_status","name":"Status"}}]}}]}}}}'
        fields_payload = '{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status","name":"Status","options":[{"id":"O_ready","name":"Ready"}]}]}}}}'

        def run_side_effect(argv, **kwargs):
            if argv[:3] == ["gh", "auth", "status"]:
                return self._completed(returncode=0, stdout="authenticated\n")
            command_text = " ".join(argv)
            if "items(first:100" in command_text:
                return self._completed(returncode=0, stdout=items_payload)
            if "fields(first:100" in command_text:
                return self._completed(returncode=0, stdout=fields_payload)
            raise AssertionError(f"Unexpected command: {argv!r}")

        with patch("subprocess.run", side_effect=run_side_effect):
            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.published), [{"summary": "matched", "count": 2}])

    def test_execute_fan_out_registers_empty_results_for_empty_array(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "args:\n  item: string\nversion: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                inputs={"items": []},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", for_each="${inputs.items}", register="nested_run", resolved_run_path=str(fragment)),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [[]])

    def test_execute_run_with_args_passes_fragment_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nargs:\n  item: string\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                inputs={"item": "demo-ref"},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(
                                name="expand",
                                run="nested.yml",
                                run_with={"item": "${inputs.item}"},
                                register="nested_run",
                                resolved_run_path=str(fragment),
                            ),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [[{"summary": "demo-ref"}]])

    def test_execute_run_with_args_may_bind_caller_step_result_without_leaking_step_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nargs:\n  item: string\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="prepare", value="demo-ref", register="issue_value"),
                            Step(
                                name="expand",
                                run="nested.yml",
                                run_with={"item": "${step.issue_value.outputs.value}"},
                                register="nested_run",
                                resolved_run_path=str(fragment),
                            ),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [[{"summary": "demo-ref"}]])

    def test_execute_run_with_args_in_for_each_passes_current_item_to_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nargs:\n  item: string\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                inputs={"items": ["one", "two"]},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(
                                name="expand",
                                run="nested.yml",
                                for_each="${inputs.items}",
                                run_with={"item": "${item}"},
                                register="nested_run",
                                resolved_run_path=str(fragment),
                            ),
                            Step(name="copy", result="${step.nested_run.results}"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [[{"results": [{"summary": "one"}]}, {"results": [{"summary": "two"}]}]])

    def test_execute_supports_standalone_gate_checkpoint_step(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="prepare", value=True, register="ready"),
                        Step(name="checkpoint", gate="step.ready.outputs.value"),
                        Step(name="done", result={"summary": "ok"}),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertIn("checkpoint", result.outputs["executed_steps"])
        self.assertEqual(list(result.results), [{"summary": "ok"}])

    def test_execute_file_loaded_run_with_args_in_for_each_passes_current_item_to_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragments = root / "fragments"
            fragments.mkdir()
            fragment = fragments / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nargs:\n  item: string\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: ${args.item}\n",
                encoding="utf-8",
            )
            caller = root / "caller.yml"
            caller.write_text(
                "version: 0\nworkflow: caller\ninputs:\n  items: []\nblocks:\n  - steps:\n      - name: expand\n        run: fragments/nested.yml\n        for_each: ${inputs.items}\n        with:\n          item: ${item}\n        register: nested_run\n      - name: copy\n        result: ${step.nested_run.results}\n",
                encoding="utf-8",
            )

            loaded = load_workflow_file(caller, launch_dir=root)
            workflow = Workflow(
                version=loaded.version,
                workflow=loaded.workflow,
                inputs={**loaded.inputs, "items": ["one", "two"]},
                declared_inputs=loaded.declared_inputs,
                let_bindings=loaded.let_bindings,
                state_needs=loaded.state_needs,
                state_bindings=loaded.state_bindings,
                states=loaded.states,
                step_results=loaded.step_results,
                blocks=loaded.blocks,
                source_path=loaded.source_path,
                launch_dir=loaded.launch_dir,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [[{"results": [{"summary": "one"}]}, {"results": [{"summary": "two"}]}]])

    def test_execute_include_fragment_with_plain_args_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragments = root / "fragments"
            fragments.mkdir()
            fragment = fragments / "emit.yml"
            fragment.write_text(
                "args:\n  item: string\nblocks:\n  - steps:\n      - name: emit\n        result:\n          summary: args.item\n",
                encoding="utf-8",
            )
            caller = root / "caller.yml"
            caller.write_text(
                "version: 0\nworkflow: caller\ninputs:\n  item: {}\nblocks:\n  - include: fragments/emit.yml\n    with:\n      item: ${inputs.item}\n",
                encoding="utf-8",
            )

            loaded = load_workflow_file(caller, launch_dir=root)
            workflow = Workflow(
                version=loaded.version,
                workflow=loaded.workflow,
                inputs={**loaded.inputs, "item": "demo-ref"},
                declared_inputs=loaded.declared_inputs,
                let_bindings=loaded.let_bindings,
                state_needs=loaded.state_needs,
                state_bindings=loaded.state_bindings,
                states=loaded.states,
                step_results=loaded.step_results,
                blocks=loaded.blocks,
                source_path=loaded.source_path,
                launch_dir=loaded.launch_dir,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.results), [{"summary": "demo-ref"}])

    def test_execute_real_parse_issue_ref_fragment_with_story_tasks_show_step_shape(self) -> None:
        root = Path(__file__).resolve().parents[1]
        caller = root / ".ordo" / "workflows" / "story-tasks-show.yml"
        loaded = load_workflow_file(caller, launch_dir=root / ".ordo")
        workflow = Workflow(
            version=loaded.version,
            workflow=loaded.workflow,
            inputs={
                **loaded.inputs,
                "active_profile_key": "active_profile",
                "issue_number": 87,
                "repo_kind": "meta",
                "repo_dir": str(root),
                "repository": "kergma-lw/checklist-meta",
                "project_id": "PVT_demo",
            },
            declared_inputs=loaded.declared_inputs,
            let_bindings={
                **loaded.let_bindings,
                "active_profile": '"meta"',
                "story_body": '"## Tasks\\n- owner/repo#1\\n- owner/repo#2"',
            },
            state_needs=loaded.state_needs,
            state_bindings=loaded.state_bindings,
            states=loaded.states,
            step_results=loaded.step_results,
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="Parse story task refs",
                            run="fragments/parse-issue-ref.yml",
                            for_each='${markdown["Tasks"].list_items with{root: story_body}}',
                            run_with={"item": "${item}"},
                            register="parsed_task_refs",
                            resolved_run_path=str(root / ".ordo" / "workflows" / "fragments" / "parse-issue-ref.yml"),
                        ),
                        Step(name="copy", result='${step.parsed_task_refs.results | field("results[0]")}'),
                    )
                ),
            ),
            source_path=loaded.source_path,
            launch_dir=loaded.launch_dir,
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(
            list(result.results),
            [[
                {"issue_ref": "owner/repo#1", "repository": "owner/repo", "issue_number": "1"},
                {"issue_ref": "owner/repo#2", "repository": "owner/repo", "issue_number": "2"},
            ]],
        )

    def test_execute_fan_out_fails_strictly_when_one_item_run_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "args:\n  item: string\nversion: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-command\n        uses: shell.command\n        with:\n          command: ${args.item}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                inputs={"items": ["ok", "boom"]},
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", for_each="${inputs.items}", register="nested_run", resolved_run_path=str(fragment)),
                        )
                    ),
                ),
            )

            def executor(resolved_step, _workflow):
                if getattr(resolved_step, "declared_with", {}).get("command") == "boom":
                    return OperationResult(status="execution_error", summary="boom")
                return OperationResult(status="ok", summary="ok")

            result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
            self.assertEqual(result.failed_step, "nested-command")
            self.assertEqual(result.outputs["fan_out_failure"]["item_index"], 1)

    def test_execute_inline_fan_out_reports_failed_item_index(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": ["ok", "boom"]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(Step(name="nested-command", operation=OperationRef("shell.command", with_={"command": "ignored"})),),
                            register="runs",
                        ),
                    )
                ),
            ),
        )

        def executor(_resolved_step, nested_workflow):
            if nested_workflow.inputs.get("__iteration_item__") == "boom":
                return OperationResult(status="execution_error", summary="boom")
            return OperationResult(status="ok", summary="ok")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "nested-command")
        self.assertEqual(result.outputs["fan_out_failure"]["item_index"], 1)
        self.assertEqual(result.outputs["fan_out_failure"]["item"], "boom")

    def test_execute_inline_fan_out_gate_failure_diagnostic_includes_item_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": ["ok", "boom"]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(Step(name="gate-item", gate='item == "ok"'),),
                            register="runs",
                        ),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertEqual(diagnostic.details["fan_out_step"], "expand")
        self.assertEqual(diagnostic.details["fan_out_item_index"], 1)
        self.assertEqual(diagnostic.details["fan_out_item"], "boom")
        self.assertEqual(diagnostic.details["human_summary"], 'Item \'boom\' failed gate \'gate-item\': item == "ok"')
        self.assertEqual(diagnostic.message, 'Item \'boom\' failed gate \'gate-item\': item == "ok"')

    def test_execute_gate_failure_diagnostic_omits_visible_registers(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="linked", value={"exists": True, "status": "Backlog"}, register="linked_project_issue"),
                        Step(
                            name="gate-linked-task",
                            gate={
                                "all": [
                                    "step.linked_project_issue.outputs.value.exists",
                                    'step.linked_project_issue.outputs.value.status | eq("Ready")',
                                ]
                            },
                        ),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertNotIn("visible_registers", diagnostic.details)

    def test_execute_gate_failure_diagnostic_surfaces_single_failed_condition_in_message(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="publish",
                            gate="git.worktree.clean",
                        ),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertEqual(diagnostic.message, "Step gate blocked execution for 'publish': git.worktree.clean")

    def test_execute_gate_failure_diagnostic_surfaces_multiple_failed_conditions_in_message(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="publish",
                            gate={"all": ["git.worktree.clean", 'git.branch.value | eq("main")']},
                        ),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertIn("git.worktree.clean", diagnostic.message)
        self.assertNotEqual(diagnostic.message, "Step gate blocked execution for 'publish'")

    def test_execute_gate_failure_diagnostic_includes_on_fail_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="gate-check",
            inputs={"repository": "kergma-lw/checklist-mobile", "issue_number": 1},
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="profile", value="mobile", register="profile"),
                        Step(name="linked", value={"exists": True, "status": "Backlog"}, register="linked_project_issue"),
                        Step(
                            name="gate-linked-task",
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

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertEqual(
            diagnostic.details["on_fail_context"],
            {
                "profile": "mobile",
                "issue_number": 1,
                "repository": "kergma-lw/checklist-mobile",
                "status": "Backlog",
            },
        )

    def test_execute_inline_fan_out_gate_failure_human_summary_supports_multiple_conditions(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="publish",
            inputs={"items": ["boom"]},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="expand",
                            for_each="${inputs.items}",
                            steps=(
                                Step(
                                    name="gate-item",
                                    gate={"all": ['item == "ok"', 'item == "good"']},
                                ),
                            ),
                            register="runs",
                        ),
                    )
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        diagnostic = next(item for item in result.diagnostics if item.code == "runtime.step.gate.failed")
        self.assertIn("Failed conditions:", diagnostic.message)
        self.assertIn('item == "ok"', diagnostic.message)
        self.assertIn('item == "good"', diagnostic.message)

    def test_execute_branch_classifiers_isolate_legacy_shaped_paths(self) -> None:
        probe = ResolvedOperation(reference="gh.issue", connector_namespace="gh", operation=OperationContract(name="issue", kind="probe"), source="public")
        action = ResolvedOperation(reference="runtime.profile.use", connector_namespace="runtime", operation=OperationContract(name="profile.use", kind="action"), source="public")
        run_step = ResolvedRunStep(name="nested", run="fragment.yml")
        builtin = ResolvedBuiltinStep(name="switch", builtin="profile_switch")

        self.assertTrue(_is_execute_probe_step({}, probe))
        self.assertFalse(_is_execute_probe_step(None, probe))
        self.assertTrue(_is_execute_run_step(run_step))
        self.assertTrue(_is_execute_profile_switch_builtin(builtin))
        self.assertTrue(_is_execute_profile_switch_operation(action))

    def test_execution_block_item_helpers_replace_inline_traversal_fragments(self) -> None:
        block = StepBlock(steps=(Step(name="a", operation=OperationRef("shell.command")), Step(name="b", operation=OperationRef("shell.command"))))
        items: list[dict[str, object]] = []

        _append_execution_error_block_item(
            items,
            block_index=0,
            declared_block=block,
            executed_steps=["a"],
            skipped_steps=["b"],
            failed_step="b",
        )
        _append_execution_ok_block_item(
            items,
            block_index=1,
            declared_block=block,
            executed_steps=["a", "b"],
            skipped_steps=[],
        )

        self.assertEqual(items[0]["status"], "execution_error")
        self.assertEqual(items[1]["status"], "ok")

    def test_initialize_execute_context_applies_profile_cleanly(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),))
        profile = Profile(name="frontend", inputs={"repo": "frontend"})

        context = _initialize_execute_context(workflow, profile=profile, profile_working_directories={"frontend": Path("/tmp")})

        self.assertEqual(context["active_profile"], "frontend")
        self.assertEqual(context["current_profile_name"], "frontend")
        self.assertEqual(context["current_working_directory"], Path("/tmp"))

    def test_initialize_execute_context_applies_workflow_declared_profile(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            profile="frontend",
            inputs={"repo": "mobile"},
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        frontend = Profile(name="frontend", inputs={"repo": "frontend"})

        context = _initialize_execute_context(
            workflow,
            profile=None,
            available_profiles={"frontend": frontend},
            profile_working_directories={"frontend": Path("/tmp/frontend")},
        )

        self.assertEqual(context["active_profile"], "frontend")
        self.assertEqual(context["current_profile_name"], "frontend")
        self.assertEqual(context["current_working_directory"], Path("/tmp/frontend"))
        self.assertEqual(context["workflow"].inputs["repo"], "frontend")

    def test_execute_uses_workflow_declared_profile_for_guards(self) -> None:
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

        result = execute_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")

    def test_execute_restores_parent_profile_after_nested_workflow_profile_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nprofile: frontend\nblocks:\n  - steps:\n      - name: nested\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", resolved_run_path=str(fragment)),
                            Step(name="switch-backend", profile_switch="backend"),
                        )
                    ),
                ),
            )
            result = execute_workflow(
                workflow,
                profile=Profile(name="backend"),
                available_profiles={"backend": Profile(name="backend"), "frontend": Profile(name="frontend")},
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "backend")

    def test_execute_workflow_profile_overrides_prior_profile_derived_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            profile="meta",
            inputs={"repository": "mobile/repo", "project_id": "mobile-project"},
            steps=(Step(name="remember", value="ok"),),
        )

        context = _initialize_execute_context(
            workflow,
            profile=Profile(name="mobile", inputs={"repository": "mobile/repo", "project_id": "mobile-project"}),
            available_profiles={
                "mobile": Profile(name="mobile", inputs={"repository": "mobile/repo", "project_id": "mobile-project"}),
                "meta": Profile(name="meta", inputs={"repository": "meta/repo", "project_id": "meta-project"}),
            },
            profile_working_directories=None,
        )

        self.assertEqual(context["active_profile"], "meta")
        self.assertEqual(context["workflow"].inputs["repository"], "meta/repo")
        self.assertEqual(context["workflow"].inputs["project_id"], "meta-project")
    def test_execute_preserves_blocked_before_execution(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        def probe(_resolved_guard, _workflow):
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

        result = execute_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode, Mode.EXECUTE)
        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_output_assembly_stays_consistent_across_blocked_and_success_paths(self) -> None:
        blocked_workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        success_workflow = Workflow(
            version=0,
            workflow="open-task",
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        blocked = execute_workflow(
            blocked_workflow,
            guard_probe=lambda *_args: OperationResult(status="guard_failed", summary="blocked"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        success = execute_workflow(
            success_workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        for key in [
            "executed_steps",
            "reused_steps",
            "skipped_steps",
            "step_condition_details",
            "launcher_details",
            "execution_tree",
            "execution_tree_mode",
            "execution_tree_fallback_reason",
        ]:
            self.assertIn(key, blocked.outputs)
            self.assertIn(key, success.outputs)

    def test_execute_runs_steps_on_success(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])
        self.assertEqual(result.outputs["execution_tree"], None)

    def test_execute_reports_step_start_before_execution(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        reported_steps: list[tuple[str, str, str | None, str | None]] = []

        def reporter(event) -> None:
            reported_steps.append((event.step_name, event.workflow_name, event.step_reference, event.working_directory))

        def executor(resolved_step, _workflow):
            self.assertEqual(reported_steps, [("effectful-step", "open-task", "shell.command", None)])
            self.assertEqual(resolved_step.reference, "shell.command")
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            step_reporter=reporter,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(reported_steps, [("effectful-step", "open-task", "shell.command", None)])

    def test_execute_propagates_step_reporting_into_nested_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-command\n        uses: shell.command\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="parent",
                guards=(),
                steps=(Step(name="expand", run="nested.yml", resolved_run_path=str(fragment)),),
            )
            reported_steps: list[tuple[str, str, bool, str | None]] = []

            def reporter(event) -> None:
                reported_steps.append((event.step_name, event.workflow_name, event.invoked_by_run, event.invoked_run_reference))

            result = execute_workflow(
                workflow,
                step_executor=lambda resolved_step, _workflow: OperationResult(status="ok", summary=resolved_step.reference),
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
                step_reporter=reporter,
            )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(
            reported_steps,
            [
                ("expand", "parent", False, None),
                ("nested-command", "parent::nested", True, "nested.yml"),
            ],
        )

    def test_execute_materializes_probe_derived_let_inputs_before_action_execution(self) -> None:
        captured_inputs: list[dict[str, object] | None] = []
        provider = ConnectorProvider(
            registry=ConnectorRegistry(
                connectors=(
                    Connector(
                        namespace="gh",
                        operations=(
                            OperationContract(
                                name="issue",
                                kind="probe",
                                inputs={"repository": "string", "issue_number": "integer"},
                                outputs={"body": "string"},
                            ),
                        ),
                    ),
                    Connector(
                        namespace="demo",
                        operations=(
                            OperationContract(name="write", kind="action", inputs={"body": "string"}),
                        ),
                    ),
                ),
            ),
            guard_probe=lambda resolved, _workflow: OperationResult(
                status="ok",
                summary="loaded issue",
                outputs={"body": "Story body from probe"},
            )
            if resolved.reference == "gh.issue"
            else OperationResult(status="ok", summary="ok"),
            step_executor=lambda resolved, _workflow: captured_inputs.append(resolved.resolved_inputs) or OperationResult(status="ok", summary="written"),
        )
        workflow = load_workflow_text(
            """
version: 0
workflow: story-task-add
inputs:
  repository: owner/repo
  issue_number: 17
let:
  story_body: gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body
blocks:
  - steps:
      - name: replace-story-body
        uses: demo.write
        with:
          body: story_body
"""
        )

        result = execute_workflow(workflow, connector_provider=provider)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(captured_inputs, [{"body": "Story body from probe"}])

    def test_execute_preserves_materialized_inputs_when_profile_is_active(self) -> None:
        captured_inputs: list[dict[str, object] | None] = []
        provider = ConnectorProvider(
            registry=ConnectorRegistry(
                connectors=(
                    Connector(
                        namespace="gh",
                        operations=(
                            OperationContract(
                                name="issue",
                                kind="probe",
                                inputs={"repository": "string", "issue_number": "integer"},
                                outputs={"body": "string"},
                            ),
                        ),
                    ),
                    Connector(
                        namespace="demo",
                        operations=(
                            OperationContract(name="write", kind="action", inputs={"body": "string"}),
                        ),
                    ),
                ),
            ),
            guard_probe=lambda resolved, _workflow: OperationResult(
                status="ok",
                summary="loaded issue",
                outputs={"body": "Story body from probe"},
            )
            if resolved.reference == "gh.issue"
            else OperationResult(status="ok", summary="ok"),
            step_executor=lambda resolved, _workflow: captured_inputs.append(resolved.resolved_inputs) or OperationResult(status="ok", summary="written"),
        )
        workflow = load_workflow_text(
            """
version: 0
workflow: story-task-add
profile: meta
inputs:
  repository: owner/repo
  issue_number: 17
let:
  story_body: gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body
blocks:
  - steps:
      - name: replace-story-body
        uses: demo.write
        with:
          body: story_body
"""
        )
        profile = Profile(name="meta")

        result = execute_workflow(
            workflow,
            profile=profile,
            available_profiles={"meta": profile},
            connector_provider=provider,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(captured_inputs, [{"body": "Story body from probe"}])

    def test_execute_runs_probe_step_without_execution_tree(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-issue",
            inputs={"repository": "kergma-lw/ordo-cli", "issue_number": 471},
            steps=(
                Step(
                    name="load-issue",
                    operation=OperationRef(
                        "gh.issue",
                        with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"},
                    ),
                    register="issue",
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.failed_step, None)
        self.assertEqual(result.outputs["executed_steps"], ["load-issue"])
        self.assertEqual(result.outputs["execution_tree"], None)
        self.assertIn("issue", workflow.step_results)

    def test_execute_probe_step_no_longer_fails_as_action_not_implemented(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-issue",
            inputs={"repository": "kergma-lw/ordo-cli", "issue_number": 471},
            steps=(
                Step(
                    name="load-issue",
                    operation=OperationRef(
                        "gh.issue",
                        with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"},
                    ),
                ),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(diagnostic.code == "operation.not_implemented" and diagnostic.details.get("kind") == "action" for diagnostic in result.diagnostics))

    def test_execute_keeps_probe_revalidation_bookkeeping_with_execution_tree(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-issue",
            inputs={"repository": "kergma-lw/ordo-cli", "issue_number": 471},
            steps=(
                Step(
                    name="load-issue",
                    operation=OperationRef(
                        "gh.issue",
                        with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"},
                    ),
                    register="issue",
                ),
            ),
        )
        probe = lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": True})
        plan_result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            guard_probe=probe,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        child = result.outputs["execution_tree"]["blocks"][0]["children"][0]
        self.assertEqual(child["runtime_status"], "revalidated")
        self.assertEqual(child["revalidated"], True)
        self.assertIn(child["divergence_status"], {"matched", "diverged"})

    def test_execute_surfaces_markdown_adapter_failure_from_value_step(self) -> None:
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

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "select")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_not_found")

    def test_execute_surfaces_text_adapter_collection_misuse_from_value_step(self) -> None:
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

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "select")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_invalid_path")

    def test_execute_surfaces_json_adapter_ambiguous_match_from_value_step(self) -> None:
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

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "select")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.adapter_ambiguous_match")

    def test_execute_accepts_plan_derived_execution_tree_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"]["workflow"], "open-task")
        self.assertEqual(result.outputs["execution_tree_mode"], "tree_assisted")
        self.assertEqual(result.outputs["execution_tree_fallback_reason"], None)

    def test_execute_falls_back_when_no_execution_tree_is_supplied(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"], None)
        self.assertEqual(result.outputs["execution_tree_mode"], "legacy_fallback")
        self.assertEqual(result.outputs["execution_tree_fallback_reason"], "missing_execution_tree")

    def test_execute_reuses_reusable_preflight_value_step_results(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${step.flag.outputs.value}"),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            step_executor=executor,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["reused_steps"], ["flag"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "reused_preflight")
        self.assertEqual(result.outputs["step_condition_details"][0]["source"], "execution_tree_state")

    def test_execute_mirrors_runtime_status_into_execution_tree_nodes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        result = execute_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "done")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][1]["children"][0]["runtime_status"], "done")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][1]["runtime_status"], "done")

    def test_execute_revalidates_probe_steps_through_execution_tree(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="inspect", operation=OperationRef("gh.issue"), register="issue"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${step.issue.outputs.exists}"),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": True} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": True} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "revalidated")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["revalidated"], True)
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_status"], "matched")
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["step_condition_details"][0]["source"], "execution_tree_state")

    def test_execute_records_divergence_for_revalidated_probe_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="inspect", operation=OperationRef("gh.issue"), register="issue"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": True} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        result = execute_workflow(
            workflow,
            guard_probe=lambda resolved_guard, _workflow: OperationResult(status="ok", outputs={"exists": False} if resolved_guard.reference == "gh.issue" else {"clean": True}),
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_status"], "diverged")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_reason"], "runtime_probe_result_mismatch")

    def test_execute_records_divergence_for_runtime_value_outputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            steps=(Step(name="flag", value=True, register="flag"),),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_status"], "matched")

    def test_execute_marks_skipped_runtime_status_in_execution_tree(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "skipped_at_run")

    def test_execution_tree_exposes_canonical_runtime_fields(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),))
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        node = result.outputs["execution_tree"]["blocks"][0]["children"][0]
        self.assertIn("runtime_status", node)
        self.assertIn("revalidated", node)
        self.assertIn("planned_probe_result", node)
        self.assertIn("runtime_probe_result", node)
        self.assertIn("divergence_status", node)
        self.assertIn("divergence_reason", node)

    def test_execute_compatibility_layer_reports_explicit_fallback(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),))

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.outputs["execution_tree_mode"], "legacy_fallback")
        self.assertEqual(result.outputs["execution_tree_fallback_reason"], "missing_execution_tree")

    def test_execute_derives_skipped_summary_from_tree_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_derives_reused_summary_from_tree_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${step.flag.outputs.value}"),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        result = execute_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.outputs["reused_steps"], ["flag"])

    def test_execute_starts_from_ready_to_run_frontier(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),)),
            ),
        )
        plan_result = plan_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )
        seen_steps: list[str] = []

        result = execute_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            step_executor=lambda resolved_step, _workflow: seen_steps.append(resolved_step.reference) or OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])

    def test_execute_without_tree_uses_legacy_checked_guard_start(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        seen_steps: list[str] = []

        result = execute_workflow(
            workflow,
            guard_probe=lambda _resolved_guard, _workflow: OperationResult(status="ok", outputs={"clean": True}),
            step_executor=lambda resolved_step, _workflow: seen_steps.append(resolved_step.reference) or OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])

    def test_execute_uses_frontier_to_skip_non_required_steps_in_same_block(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="flag", value=True, register="flag"),
                        Step(name="effectful-step", operation=OperationRef("shell.command")),
                    )
                ),
            ),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        plan_result.outputs["execution_tree"]["ready_to_run_frontier"]["requires_runtime_node_ids"] = ["block:0:step:1"]
        seen_steps: list[str] = []

        result = execute_workflow(
            workflow,
            step_executor=lambda resolved_step, _workflow: seen_steps.append(resolved_step.reference) or OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])

    def test_execute_normalizes_step_failure(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command")),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )
        call_count = 0

        def executor(_resolved_step, _workflow):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OperationResult(status="execution_error", summary="Boom", raw={"stderr": "failed"})
            return OperationResult(status="ok")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.operation_results[-1].raw["stderr"], "failed")

    def test_execute_skips_step_when_condition_is_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, [])
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_runs_step_when_condition_is_true(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": True},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_fails_when_step_condition_cannot_be_evaluated(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"enabled": {}},
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.diagnostics[-1].code, "runtime.value.input_missing")

    def test_execute_profile_switch_rejects_unknown_bare_object_reference(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - steps:
      - name: switch
        profile_switch: meta
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "switch")
        self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.value.reference_unknown")

    def test_execute_applies_launcher_to_shell_command(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command", with_={"command": "echo hi"}), launcher="shell_frontend"),),
        )
        profile = Profile(name="frontend", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use", after="true")})
        seen_commands: list[object] = []

        def executor(resolved_step, _workflow):
            seen_commands.append(resolved_step.declared_with["command"])
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, profile=profile, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(len(seen_commands), 1)
        self.assertIn("nvm use", seen_commands[0])
        self.assertIn("echo hi", seen_commands[0])
        self.assertEqual(result.outputs["launcher_details"][0]["launcher"], "shell_frontend")

    def test_execute_reports_unknown_launcher_as_validation_error(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command", with_={"command": "echo hi"}), launcher="missing"),),
        )
        profile = Profile(name="frontend")

        result = execute_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "validation.workflow.step.launcher.unknown")

    def test_execute_runtime_profile_use_switches_profile_for_nested_run_and_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend_dir = root / "frontend"
            backend_dir = root / "backend"
            frontend_dir.mkdir()
            backend_dir.mkdir()
            fragment = root / "fragment.yml"
            fragment.write_text(
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: \"echo hi\"\n    launcher: shell_frontend\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                source_path=str(root / "root.yml"),
                launch_dir=str(root),
                guards=(),
                steps=(
                    Step(name="switch", operation=OperationRef("runtime.profile.use", with_={"profile": "frontend"})),
                    Step(name="nested", run="fragment.yml", resolved_run_path=str(fragment)),
                ),
            )
            backend = Profile(name="backend")
            frontend = Profile(name="frontend", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use", after="true")})
            seen = []

            def executor(resolved_step, _workflow):
                seen.append((resolved_step.reference, Path.cwd(), resolved_step.declared_with.get("command")))
                return OperationResult(status="ok", summary="Executed")

            result = execute_workflow(
                workflow,
                profile=backend,
                available_profiles={"backend": backend, "frontend": frontend},
                profile_working_directories={"backend": backend_dir, "frontend": frontend_dir},
                step_executor=executor,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "frontend")
            self.assertEqual(seen[0][0], "shell.command")
            self.assertEqual(seen[0][1], frontend_dir)
            self.assertIn("nvm use", seen[0][2])

    def test_execute_marks_nested_run_and_profile_switch_statuses_in_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "fragment.yml"
            fragment.write_text(
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: \"echo hi\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                source_path=str(root / "root.yml"),
                launch_dir=str(root),
                steps=(
                    Step(name="switch", profile_switch="frontend"),
                    Step(name="nested", run="fragment.yml", resolved_run_path=str(fragment)),
                ),
            )
            frontend = Profile(name="frontend")
            plan_result = plan_workflow(
                workflow,
                available_profiles={"frontend": frontend},
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            result = execute_workflow(
                workflow,
                available_profiles={"frontend": frontend},
                step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
                execution_tree=plan_result.outputs["execution_tree"],
            )

            self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "done")
            self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][1]["runtime_status"], "done")

    def test_execute_marks_failed_step_status_in_tree(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="execution_error", summary="boom"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["runtime_status"], "failed")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_pre_run_workflow_can_switch_profile_for_main_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            frontend_dir = root / "frontend"
            backend_dir = root / "backend"
            frontend_dir.mkdir()
            backend_dir.mkdir()
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\npre_run:\n  - file: workflows/resolve-context.yml\ndefaults:\n  profile: backend\nworkflows:\n  close-task:\n    file: close-task.yml\nprofiles:\n  frontend:\n    file: frontend.yml\n  backend:\n    file: backend.yml\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "steps:\n  - name: switch\n    profile_switch: \"frontend\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                "version: 0\nworkflow: close-task\ninputs:\n  repo_dir: {}\nblocks:\n  - steps:\n      - name: main\n        uses: shell.command\n        with:\n          command: \"echo hi\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text(
                "name: frontend\ninputs:\n  repo_dir: ../frontend\nworking_directory: ${inputs.repo_dir}\nlaunchers:\n  shell_frontend:\n    before: nvm use\n    after: \"true\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repo_dir: ../backend\nworking_directory: ${inputs.repo_dir}\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="close-task", cwd=root)
            seen = []

            def executor(resolved_step, _workflow):
                seen.append((resolved_step.reference, Path.cwd(), resolved_step.declared_with.get("command"), dict(_workflow.inputs)))
                return OperationResult(status="ok", summary="Executed")

            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                step_executor=executor,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "frontend")
            self.assertEqual(seen[0][1], frontend_dir)
            self.assertEqual(seen[0][3]["repo_dir"], "../frontend")

    def test_execute_pre_run_profile_switch_reapplies_profile_inputs_to_parent_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "meta"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\npre_run:\n  - file: workflows/switch-active-profile.yml\n    state_bindings:\n      shared_state: shared_state\ndefaults:\n  profile: backend\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\n    state_bindings:\n      shared_state: shared_state\nprofiles:\n  backend:\n    file: backend.yml\n  meta:\n    file: meta.yml\nstates:\n  shared_state:\n    path: repo.json\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  active_profile_key: active_profile\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == \"kergma-lw/checklist-meta\"\n  - steps:\n      - name: main\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repository: kergma-lw/checklist-backend\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "meta.yml").write_text(
                "name: meta\ninputs:\n  repository: kergma-lw/checklist-meta\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)
            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "meta")
            self.assertIn("main", result.outputs["executed_steps"])

    def test_execute_explicit_cli_profile_wins_over_pre_run_profile_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend_dir = root / "backend"
            meta_dir = root / "meta"
            backend_dir.mkdir()
            meta_dir.mkdir()
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "meta"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\npre_run:\n  - file: workflows/switch-active-profile.yml\n    state_bindings:\n      shared_state: shared_state\ndefaults:\n  profile: backend\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\n    state_bindings:\n      shared_state: shared_state\nprofiles:\n  backend:\n    file: backend.yml\n  meta:\n    file: meta.yml\nstates:\n  shared_state:\n    path: repo.json\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  active_profile_key: active_profile\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == \"kergma-lw/checklist-backend\"\n  - steps:\n      - name: main\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                f"name: backend\ninputs:\n  repository: kergma-lw/checklist-backend\n  repo_dir: {backend_dir}\nworking_directory: ${{inputs.repo_dir}}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "meta.yml").write_text(
                f"name: meta\ninputs:\n  repository: kergma-lw/checklist-meta\n  repo_dir: {meta_dir}\nworking_directory: ${{inputs.repo_dir}}\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="backend", cwd=root)
            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "backend")
        self.assertEqual(result.outputs["current_working_directory"], str(backend_dir))
        self.assertIn("main", result.outputs["executed_steps"])

    def test_runtime_profile_use_applies_profile_inputs_to_subsequent_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            guards=(),
            steps=(
                Step(name="switch", operation=OperationRef("runtime.profile.use", with_={"profile": "frontend"})),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repository"], "profile/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_execute_profile_switch_injects_profile_inputs_when_not_explicitly_overridden(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repository"], "profile/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_execute_profile_switch_preserves_explicit_input_overrides(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            declared_inputs={"repository": {}},
            explicit_input_keys=("repository",),
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repository"], "explicit/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_execute_profile_switch_reapplies_context_after_repeated_switches(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="switch-frontend", profile_switch="frontend"),
                Step(name="switch-backend", profile_switch="backend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend", inputs={"repo_kind": "backend"})
        frontend = Profile(name="frontend", inputs={"repo_kind": "frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "backend")
        self.assertEqual(seen_inputs[0]["repo_kind"], "backend")

    def test_execute_profile_switch_uses_prior_step_output(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="select-profile", value="frontend", register="selected"),
                Step(name="switch", profile_switch="${step.selected.outputs.value}"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repo_kind": "frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repo_kind"], "frontend")


if __name__ == "__main__":
    unittest.main()
