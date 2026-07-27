import unittest
from pathlib import Path

from ordo.model.runtime import RuntimeStatus
from ordo.runtime import validate_workflow_text


ROOT = Path(__file__).resolve().parents[1]


class ProjectItemsExampleTest(unittest.TestCase):
    def test_project_items_let_example_validates(self) -> None:
        example_path = ROOT / "examples" / "project-items-let.yaml"

        report = validate_workflow_text(example_path.read_text(encoding="utf-8"), source=str(example_path))

        self.assertEqual(report.status, RuntimeStatus.OK)


if __name__ == "__main__":
    unittest.main()
