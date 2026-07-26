import unittest

from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ReviewModeTest(unittest.TestCase):
    def test_review_reports_missing_input_validation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "needs_attention")
        self.assertTrue(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))

    def test_review_reports_missing_recommended_observations(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "In review",
                                },
                            ),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(any(item["code"] == "review.workflow.missing_recommended_observations" for item in result.outputs["findings"]))

    def test_review_reports_clean_when_no_findings_exist(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            blocks=(
                GuardBlock(guards=(Guard(expr="inputs.repository | is_string"),)),
                StepBlock(
                    steps=(
                        Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),
                    )
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "clean")
        self.assertEqual(result.outputs["finding_count"], 0)
        self.assertEqual(result.outputs["findings"], [])
