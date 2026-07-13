import tempfile
import unittest
from pathlib import Path

from ordo.model.workflow import Step, Workflow
from ordo.runtime.fragment_runs import classify_run_for_check


class FragmentRunClassificationTest(unittest.TestCase):
    def test_classifies_profile_switch_fragment_as_check_expandable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "profile-switch.yml"
            fragment.write_text(
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
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
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
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

    def test_classifies_effectful_fragment_as_not_check_analyzable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragment = root / "effectful.yml"
            fragment.write_text(
                "steps:\n  - name: main\n    uses: shell.command\n    with:\n      command: echo hi\n",
                encoding="utf-8",
            )
            workflow = Workflow(version=0, workflow="root", steps=(Step(name="expand", run="effectful.yml", resolved_run_path=str(fragment)),))

            decision = classify_run_for_check(workflow.steps[0], workflow, block_index=0, step_index=0)

            self.assertFalse(decision.admissible)
            self.assertEqual(decision.reason, "run_subtree_requires_effectful_execution")


if __name__ == "__main__":
    unittest.main()
