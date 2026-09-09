import os
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.model.workflow import OperationRef, Step, StepBlock, Workflow
from ordo.runtime import execute_workflow
from ordo.routines import inspect_routine

from tests.support import STANDARD_CONNECTOR_PROVIDER


ROOT = Path(__file__).resolve().parents[1]


class ProjectRoutineTest(unittest.TestCase):
    def test_project_routine_catalog_includes_uncovered_snippet_probe(self) -> None:
        entry = inspect_routine("help.snippet-coverage.uncovered-list", cwd=ROOT)

        self.assertEqual(entry.kind, "probe")
        self.assertEqual(entry.outputs["mode"], "data")
        self.assertEqual(entry.outputs["format"], "json")

    def test_project_uncovered_snippet_probe_returns_structured_data(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-uncovered-help-snippets",
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="list-uncovered-help-snippets",
                            operation=OperationRef("routine.help.snippet-coverage.uncovered-list"),
                        ),
                    )
                ),
            ),
            launch_dir=str(ROOT),
        )

        # Exercise this checkout's launcher, not a developer-installed command.
        with patch.dict(os.environ, {"PATH": str(ROOT) + os.pathsep + os.environ.get("PATH", "")}):
            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok", repr(result))
        outputs = result.operation_results[0].outputs["data"]
        self.assertIn("total_none", outputs)
        self.assertIn("by_topic", outputs)
        self.assertIn("handles", outputs)


if __name__ == "__main__":
    unittest.main()
