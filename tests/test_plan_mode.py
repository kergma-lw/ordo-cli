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
        self.assertEqual(result.outputs["step_items"][0]["invalidates_scopes"], ["gh.*"])

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

    def test_plan_reports_undeclared_root_input_inside_run_target_as_validation_error(self) -> None:
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

            result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
            self.assertEqual(result.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")

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

    def test_plan_marks_context_applied_run_as_context_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "switch-profile.yml"
            fragment.write_text(
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                declared_inputs={"repo_kind": {}},
                blocks=(
                    StepBlock(steps=(Step(name="expand", run="switch-profile.yml", resolved_run_path=str(fragment)),)),
                    GuardBlock(guards=(Guard(expr='inputs.repo_kind == "frontend"'),)),
                ),
            )
            profiles = {"frontend": Profile(name="frontend", inputs={"repo_kind": "frontend"})}

            result = plan_workflow(workflow, available_profiles=profiles, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.outputs["step_items"][0]["preflight_classification"], "context_only")

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

    def test_plan_attaches_observation_scopes_to_read_only_steps(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(), steps=(Step(name="inspect", operation=OperationRef("gh.issue")),))

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_items"][0]["observation_scopes"], ["gh.issue"])
        self.assertEqual(result.outputs["step_items"][0]["invalidates_scopes"], [])

    def test_plan_derives_reuse_policy_for_preflight_knowledge(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(
                    steps=(
                        Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),
                        Step(name="derive-flag", value=True, register="flag"),
                        Step(name="close-issue", operation=OperationRef("gh.issue.close")),
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

        self.assertEqual(result.outputs["preflight_step_items"][0]["reuse_policy"], "revalidate")
        self.assertEqual(result.outputs["preflight_step_items"][1]["reuse_policy"], "reusable")
        self.assertEqual(result.outputs["step_items"][2]["reuse_policy"], "not_reusable")

    def test_plan_links_guards_to_supporting_preflight_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 1},
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
                GuardBlock(
                    guards=(
                        Guard(
                            expr='gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).number == 1'
                        ),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"number": 1})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["guard_items"][0]["supporting_step_names"], ["load-issue"])
        self.assertEqual(result.outputs["guard_items"][0]["supporting_value_paths"], ["step.issue.outputs.number"])
        self.assertEqual(result.outputs["preflight_step_items"][0]["produced_registers"], ["issue"])
        self.assertEqual(result.outputs["preflight_step_items"][0]["produced_value_paths"], ["step.issue.outputs.number"])

    def test_plan_assembles_execution_oriented_tree_artifact(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="load-issue", operation=OperationRef("gh.issue"), register="issue"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        tree = result.outputs["execution_tree"]
        self.assertEqual(tree["workflow"], "open-task")
        self.assertEqual(tree["blocks"][0]["id"], "block:0")
        self.assertEqual(tree["blocks"][0]["runtime_status"], "not_started")
        self.assertEqual(tree["blocks"][0]["children"][0]["id"], "block:0:step:0")
        self.assertEqual(tree["blocks"][0]["children"][0]["runtime_status"], "not_started")
        self.assertEqual(tree["blocks"][0]["children"][0]["revalidated"], False)
        self.assertEqual(tree["blocks"][0]["children"][0]["preflight"]["register"], "issue")
        self.assertEqual(tree["blocks"][0]["children"][0]["divergence_status"], "not_checked")
        self.assertEqual(tree["blocks"][0]["children"][0]["runtime_observation"], None)
        self.assertEqual(tree["blocks"][1]["children"][0]["id"], "block:1:guard:0")
        self.assertEqual(tree["blocks"][1]["children"][0]["runtime_status"], "not_started")
        self.assertEqual(tree["blocks"][1]["children"][0]["divergence_status"], "not_applicable")

    def test_plan_marks_freshness_and_invalidation_state_on_tree_nodes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 1},
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"})),),
            steps=(
                Step(
                    name="close",
                    operation=OperationRef("gh.issue.close", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.issue_number}"}),
                ),
            ),
        )

        def probe(_resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"state": "OPEN"})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["guard_items"][0]["freshness_state"], "stale")
        self.assertEqual(result.outputs["step_items"][0]["freshness_state"], "not_applicable")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["freshness_state"], "stale")
        self.assertEqual(result.outputs["step_items"][0]["invalidates_scopes"], ["gh.*"])

    def test_plan_builds_ready_to_run_frontier(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            blocks=(
                StepBlock(steps=(Step(name="flag", value=True, register="flag"),)),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="ship", operation=OperationRef("shell.command")),)),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "gh.issue":
                return OperationResult(status="ok", outputs={"exists": True})
            return OperationResult(status="ok", outputs={"clean": True})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        frontier = result.outputs["ready_to_run_frontier"]
        self.assertEqual(frontier["allowed_state"], "allowed")
        self.assertIn("block:0:step:0", frontier["prepared_node_ids"])
        self.assertIn("block:2:step:0", frontier["requires_runtime_node_ids"])

    def test_plan_frontier_reports_blocked_nodes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='git.branch.value != "main"'),),
            steps=(Step(name="ship", operation=OperationRef("shell.command")),),
        )

        def probe(_resolved_guard, _workflow):
            return OperationResult(status="ok", outputs={"value": "main"})

        result = plan_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        frontier = result.outputs["ready_to_run_frontier"]
        self.assertIn("block:0:guard:0", frontier["blocked_node_ids"])

    def test_plan_keeps_unknown_preflight_classification_for_unresolved_operations(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.outputs["step_items"][0]["preflight_classification"], "unknown")

    def test_plan_records_known_fan_out_cardinality_on_run_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            inputs={"items": ["one", "two", "three"]},
            steps=(Step(name="inspect", run="fragment.yml", for_each="${inputs.items}", register="runs"),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        fan_out = result.outputs["step_items"][0]["fan_out"]
        self.assertEqual(fan_out["source_status"], "static_known")
        self.assertEqual(fan_out["item_count"], 3)
        self.assertEqual(fan_out["register_mode"], "aggregate_results")
        self.assertEqual(result.outputs["execution_tree"]["blocks"][0]["children"][0]["fan_out"]["item_count"], 3)

    def test_plan_marks_runtime_only_fan_out_when_cardinality_is_not_statically_known(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            steps=(Step(name="inspect", run="fragment.yml", for_each="${state.memory.items}", register="runs"),),
        )

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        fan_out = result.outputs["step_items"][0]["fan_out"]
        self.assertEqual(fan_out["source_status"], "runtime_only")
        self.assertIsNone(fan_out["item_count"])

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
