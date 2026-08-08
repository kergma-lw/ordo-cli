import tempfile
import unittest
from pathlib import Path

from ordo.model.diagnostic import Diagnostic
from ordo.model.workflow import Step, Workflow
from ordo.runtime.fragment_runs import classify_run_for_check, materialize_run_workflow


class FragmentRunClassificationTest(unittest.TestCase):
    def test_classifies_profile_switch_fragment_as_check_expandable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-switch.yml"
            fragment.write_text(
                "steps:\n  - name: switch\n    profile_switch: \"frontend\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(version=0, workflow="root", steps=(Step(name="expand", run="profile-switch.yml", resolved_run_path=str(fragment)),))

            decision = classify_run_for_check(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertTrue(decision.admissible)
            self.assertEqual(decision.reason, "run_expandable")
            self.assertIsNotNone(decision.workflow)

    def test_classifies_unknown_run_bindings_as_not_known(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-switch.yml"
            fragment.write_text(
                "steps:\n  - name: switch\n    profile_switch: \"frontend\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="root",
                steps=(Step(name="expand", run="profile-switch.yml", resolved_run_path=str(fragment), run_with={"profile": "${inputs.profile}"}),),
            )

            decision = classify_run_for_check(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertFalse(decision.admissible)
            self.assertEqual(decision.reason, "run_args_not_known")

    def test_classifies_effectful_fragment_as_check_expandable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "effectful.yml"
            fragment.write_text(
                "steps:\n  - name: main\n    uses: shell.command\n    with:\n      command: \"echo hi\"\n",
                encoding="utf-8",
            )
            workflow = Workflow(version=0, workflow="root", steps=(Step(name="expand", run="effectful.yml", resolved_run_path=str(fragment)),))

            decision = classify_run_for_check(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertTrue(decision.admissible)
            self.assertEqual(decision.reason, "run_expandable")

    def test_classifies_missing_fragment_as_not_loadable(self) -> None:
        workflow = Workflow(version=0, workflow="root", steps=(Step(name="expand", run="missing.yml", resolved_run_path="/tmp/does-not-exist.yml"),))

        decision = classify_run_for_check(workflow.steps[0], workflow, block_index=0, step_index=0)

        self.assertFalse(decision.admissible)
        self.assertEqual(decision.reason, "run_target_not_loadable")

    def test_materialized_full_run_workflow_keeps_nested_let_and_state_but_not_caller_step_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "switch-active-profile.yml"
            fragment.write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="root",
                inputs={"repo_kind": "backend"},
                declared_inputs={"repo_kind": {}},
                let_bindings={"caller_value": 'inputs.repo_kind == "backend"'},
                state_needs={"caller_state": {}},
                state_bindings={"shared_state": "shared_state"},
                states={"shared_state": {"path": "repo.json"}, "caller_state": {"path": "caller.json"}},
                step_results={"existing": {"value": "ok"}},
                steps=(Step(name="expand", run="switch-active-profile.yml", resolved_run_path=str(fragment)),),
            )

            materialized = materialize_run_workflow(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertIsInstance(materialized, Workflow)
            assert isinstance(materialized, Workflow)
            self.assertEqual(materialized.inputs["repo_kind"], "backend")
            self.assertEqual(materialized.inputs["active_profile_key"], "active_profile")
            self.assertEqual(materialized.let_bindings["active_profile"], "state.shared_state[inputs.active_profile_key]")
            self.assertNotIn("caller_value", materialized.let_bindings)
            self.assertIn("caller_state", materialized.state_needs)
            self.assertIn("shared_state", materialized.state_needs)
            self.assertEqual(materialized.state_bindings["shared_state"], "shared_state")
            self.assertIn("caller_state", materialized.states)
            self.assertEqual(materialized.step_results, {})

    def test_materialized_run_workflow_rejects_direct_caller_step_reference_in_named_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "nested.yml"
            fragment.write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-result\n        value: ${step.issue.outputs.id}\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="root",
                step_results={"issue": {"outputs": {"id": 17}}},
                steps=(Step(name="expand", run="nested.yml", resolved_run_path=str(fragment)),),
            )

            materialized = materialize_run_workflow(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertIsInstance(materialized, Diagnostic)
            assert isinstance(materialized, Diagnostic)
            self.assertEqual(materialized.code, "load.workflow.run.step_scope")


if __name__ == "__main__":
    unittest.main()
