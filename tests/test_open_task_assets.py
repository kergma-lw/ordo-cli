from pathlib import Path
import unittest

from ordo.runtime import load_workflow_file, validate_profile_text, validate_workflow_text
from ordo.model.runtime import RuntimeStatus


ROOT = Path(__file__).resolve().parents[1]


class OpenTaskAssetTest(unittest.TestCase):
    def test_open_task_example_validates(self) -> None:
        path = ROOT / "examples" / "open-task-from-gitx.yaml"

        report = validate_workflow_text(path.read_text(encoding="utf-8"), source=str(path))

        self.assertEqual(report.status, RuntimeStatus.OK)

    def test_open_task_profiles_validate(self) -> None:
        for name in ("checklist-backend-open-task.yaml", "checklist-frontend-open-task.yaml"):
            path = ROOT / "profiles" / name

            report = validate_profile_text(path.read_text(encoding="utf-8"), source=str(path))

            self.assertEqual(report.status, RuntimeStatus.OK, name)

    def test_bundled_ordo_workflows_load_with_fragment_assets(self) -> None:
        for name in ("open-task.yml", "close-task.yml"):
            path = ROOT / ".ordo" / "workflows" / name

            workflow = load_workflow_file(path)

            self.assertTrue(workflow.blocks, name)


if __name__ == "__main__":
    unittest.main()
