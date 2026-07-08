import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import check_workflow, execute_workflow, load_workflow_file, plan_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class FragmentRunTest(unittest.TestCase):
    def test_check_workflow_preserves_run_block_as_distinct_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - guards: []
                      - run: fragments/comment
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "comment.yaml").write_text("steps: []\n", encoding="utf-8")

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["block_items"][1]["type"], "run")
        self.assertEqual(result.outputs["block_items"][1]["reference"], "fragments/comment")

    def test_plan_workflow_reports_run_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - guards: []
                      - run: fragments/comment
                        if: ${inputs.enabled}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "comment.yaml").write_text("steps: []\n", encoding="utf-8")

            workflow = load_workflow_file(workflow_path, launch_dir=root)
            workflow.inputs["enabled"] = True

        result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["run_items"][0]["reference"], "fragments/comment")
        self.assertTrue(result.outputs["run_items"][0]["conditional"])

    def test_execute_workflow_runs_fragment_with_caller_scoped_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - steps:
                          - name: derive-message
                            value: hello
                            register: message
                      - run: fragments/comment
                        if: ${step.message.outputs.value | eq("hello")}
                        with:
                          comment: ${step.message.outputs.value}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "comment.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      comment: string
                    steps:
                      - name: remember-comment
                        value: ${args.comment}
                        register: remembered
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)
            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertIn("derive-message", result.outputs["executed_steps"])
            self.assertIn("remember-comment", result.outputs["executed_steps"])
            run_items = [item for item in result.outputs["block_items"] if item.get("type") == "run"]
            self.assertTrue(run_items)
            self.assertEqual(run_items[-1]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
