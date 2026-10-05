import unittest
from unittest.mock import patch

from ordo.model.profile import Profile
from ordo.model.workflow import Guard, GuardBlock, Step, StepBlock, Workflow
from ordo.runtime.reviewing import _build_static_review_findings, review_workflow

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


class StaticReviewingTest(unittest.TestCase):
    def test_static_builder_does_not_require_runtime_analysis(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-many",
            profile="project-local",
            declared_inputs={"items": {}},
            steps=(
                Step(
                    name="inspect",
                    for_each="${inputs.items}",
                    steps=(
                        Step(name="capture", value="${item}", register="item_value"),
                        Step(name="copy", value="${step.item_value.outputs.value}", register="copied"),
                        Step(name="publish", result={"summary": "${step.copied.outputs.value}"}),
                    ),
                    register="runs",
                ),
            ),
        )

        with patch("ordo.runtime.reviewing.check_workflow") as check:
            findings = _build_static_review_findings(workflow)

        check.assert_not_called()

        self.assertEqual([item["code"] for item in findings.workflow_profile_bindings], ["review.workflow.profile.project_local_binding"])
        self.assertEqual([item["code"] for item in findings.input_descriptions], ["review.workflow.input_description_missing"])
        self.assertEqual([item["code"] for item in findings.inline_fan_out_complexity], ["review.workflow.fan_out.inline_body_complexity"])


if __name__ == "__main__":
    unittest.main()
