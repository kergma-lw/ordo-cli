import textwrap
import unittest

from ordo.runtime import check_workflow, load_workflow_text, review_workflow
from tests.support import STANDARD_CONNECTOR_PROVIDER


class OptionalInputReviewTest(unittest.TestCase):
    def test_check_analysis_tree_publishes_required_and_default_metadata_for_inputs(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  repository:
                    required: true
                  close_comment:
                    required: false
                  ship:
                    required: false
                    default: false
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          repository: ${inputs.repository}
                """
            )
        )

        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        usages = {item["input"]: item for item in result.analysis_tree.input_usages}

        self.assertTrue(usages["repository"]["required"])
        self.assertFalse(usages["repository"]["has_default"])
        self.assertFalse(usages["close_comment"]["required"])
        self.assertFalse(usages["close_comment"]["has_default"])
        self.assertFalse(usages["ship"]["required"])
        self.assertTrue(usages["ship"]["has_default"])

    def test_review_skips_missing_validation_warning_for_optional_input_with_default(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  close_comment:
                    required: false
                    default: ""
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          body: ${inputs.close_comment}
                """
            )
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        finding_codes = {item["code"] for item in result.outputs["findings"]}

        self.assertNotIn("review.workflow.input_validation_missing", finding_codes)
        self.assertNotIn("review.workflow.optional_input_presence_guard_missing", finding_codes)

    def test_review_warns_when_optional_input_without_default_is_consumed_without_guard(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  close_comment:
                    required: false
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          body: ${inputs.close_comment}
                """
            )
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.optional_input_presence_guard_missing")

        self.assertEqual(finding["path"], ["inputs", "close_comment"])
        self.assertEqual(finding["evidence"]["suggested_rewrite"], {"guards": ["is_present(inputs.close_comment)"]})

    def test_review_keeps_required_input_validation_warning(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  repository:
                    required: true
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          repository: ${inputs.repository}
                """
            )
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        finding = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.input_validation_missing")

        self.assertEqual(finding["path"], ["inputs", "repository"])
        self.assertTrue(finding["evidence"]["required"])
