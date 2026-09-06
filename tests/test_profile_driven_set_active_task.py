import unittest
from pathlib import Path

from ordo.playbook import activate_playbook
from ordo.runtime.reviewing import review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


ROOT = Path(__file__).resolve().parents[1]


class ProfileDrivenSetActiveTaskTest(unittest.TestCase):
    def test_set_active_task_has_only_input_documentation_findings_from_profile_plus_issue_number_entry(self) -> None:
        activated = activate_playbook(
            workflow_name="set-active-task",
            profile_name="ordo",
            input_overrides={"issue_number": 106},
            cwd=ROOT,
        )

        result = review_workflow(
            activated.workflow,
            profile=activated.profile,
            available_profiles=activated.available_profiles,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.outputs["active_profile"], "ordo")
        self.assertFalse([
            item for item in result.outputs["findings"]
            if item["code"] != "review.workflow.input_description_missing"
        ])


if __name__ == "__main__":
    unittest.main()
