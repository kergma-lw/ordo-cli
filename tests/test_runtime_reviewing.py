import unittest

from ordo.model.profile import Profile
from ordo.model.workflow import Guard, GuardBlock, Step, StepBlock, Workflow
from ordo.runtime.reviewing import review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeReviewingProfileSwitchTest(unittest.TestCase):
    def test_review_treats_switched_profile_repository_as_trusted_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"profile": "backend", "repository": "declared/repo"},
            declared_inputs={"profile": {}, "repository": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'),)),
                StepBlock(steps=(Step(name="switch", profile_switch="backend"),)),
                StepBlock(steps=(Step(name="publish", publish={"repository": "${inputs.repository}"}),)),
            ),
        )
        backend = Profile(name="backend", inputs={"repository": "backend/repo"})

        result = review_workflow(workflow, profile=None, available_profiles={"backend": backend}, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status.value, "ok")
        self.assertEqual(result.outputs["active_profile"], "backend")
        repository_findings = [item for item in result.outputs["findings"] if item.get("path") == ["inputs", "repository"]]
        self.assertEqual(repository_findings, [])

    def test_review_preserves_warning_for_explicit_repository_override_after_switch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"profile": "backend", "repository": "override/repo"},
            declared_inputs={"profile": {}, "repository": {}},
            explicit_input_keys=("repository",),
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'),)),
                StepBlock(steps=(Step(name="switch", profile_switch="backend"),)),
                StepBlock(steps=(Step(name="publish", publish={"repository": "${inputs.repository}"}),)),
            ),
        )
        backend = Profile(name="backend", inputs={"repository": "backend/repo"})

        result = review_workflow(workflow, profile=None, available_profiles={"backend": backend}, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        repository_findings = [item for item in result.outputs["findings"] if item.get("path") == ["inputs", "repository"]]
        self.assertEqual(len(repository_findings), 1)


if __name__ == "__main__":
    unittest.main()
