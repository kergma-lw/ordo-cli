import unittest

from ordo.introspection import describe_capabilities
from ordo.runtime.validation import validate_workflow_text


class IntrospectionNegativeRulesTest(unittest.TestCase):
    def test_negative_rules_cover_high_value_validation_failures(self) -> None:
        payload = describe_capabilities()
        rules = {item["name"]: item for item in payload["negative_rules"]}

        mixed_form_report = validate_workflow_text(
            "version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps:\n      - name: bad\n        uses: gh.issue\n        state_delete: state.memory[inputs.issue]\n"
        )
        with_without_uses_report = validate_workflow_text(
            "version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps:\n      - name: bad\n        state_delete: state.memory[inputs.issue]\n        with:\n          issue: ${inputs.issue}\n"
        )
        guard_step_ref_report = validate_workflow_text(
            "version: 0\nworkflow: demo\nblocks:\n  - guards:\n      - step.issue.outputs.id == 1\n  - steps: []\n"
        )
        forward_step_ref_report = validate_workflow_text(
            "version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps:\n      - name: later\n        uses: gh.issue.comment\n        with:\n          issue_id: ${step.issue.outputs.id}\n      - name: inspect\n        uses: gh.issue\n        register: issue\n"
        )
        format_args_report = validate_workflow_text(
            "version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps:\n      - name: open\n        uses: gh.issue\n        with:\n          title:\n            format: hi {0}\n            args: nope\n"
        )

        self.assertEqual(mixed_form_report.diagnostics[0].code, rules["workflow_step.exactly_one_form"]["related_codes"][0])
        self.assertEqual(with_without_uses_report.diagnostics[0].code, rules["workflow_step.with_requires_uses"]["related_codes"][0])
        self.assertEqual(guard_step_ref_report.diagnostics[0].code, rules["guard_expression.no_step_root"]["related_codes"][0])
        self.assertEqual(forward_step_ref_report.diagnostics[0].code, rules["value_expression.step_refs_must_be_backward"]["related_codes"][0])
        self.assertEqual(format_args_report.diagnostics[0].code, rules["format_value.args_must_be_list"]["related_codes"][0])


if __name__ == "__main__":
    unittest.main()
