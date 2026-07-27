import unittest
from pathlib import Path
import tempfile

from ordo.model.diagnostic import Diagnostic
from ordo.model.launcher import Launcher
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.playbook import activate_playbook
from ordo.runtime import execute_workflow, plan_workflow
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
from ordo.runtime.resolution import ResolvedBuiltinStep, ResolvedOperation, ResolvedRunStep
from ordo.model.connector import OperationContract

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExecuteModeTest(unittest.TestCase):
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
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: nested\n",
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

    def test_execute_does_not_emit_fallback_results_for_nested_run_without_explicit_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-value\n        value: ok\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="publish",
                blocks=(
                    StepBlock(
                        steps=(
                            Step(name="expand", run="nested.yml", resolved_run_path=str(fragment)),
                            Step(name="remember", value="done"),
                        )
                    ),
                ),
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.results), [])

    def test_execute_registers_results_from_run_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        result:\n          summary: nested\n",
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
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["divergence_reason"], "runtime_observation_mismatch")

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
        self.assertIn("planned_observation", node)
        self.assertIn("runtime_observation", node)
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
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: echo hi\n    launcher: shell_frontend\n",
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
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: echo hi\n",
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
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                "version: 0\nworkflow: close-task\ninputs:\n  repo_dir: {}\nblocks:\n  - steps:\n      - name: main\n        uses: shell.command\n        with:\n          command: echo hi\n",
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
                seen.append((resolved_step.reference, Path.cwd(), resolved_step.declared_with.get("command")))
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
        self.assertEqual(seen_inputs[0]["repository"], "explicit/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_execute_profile_switch_applies_profile_inputs_to_subsequent_steps(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
