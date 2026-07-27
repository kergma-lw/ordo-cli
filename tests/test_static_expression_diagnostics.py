import unittest

from ordo.runtime.static_expression_diagnostics import collect_static_expression_diagnostics


class StaticExpressionDiagnosticsTest(unittest.TestCase):
    def test_collects_statically_known_format_placeholder_mismatch(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            {"format": "%s#%s", "args": ["repo-only"]},
            path=("blocks", "0", "steps", "0", "publish", "issue_ref"),
            source="demo.yml",
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].code, "validation.workflow.value_expr.format.placeholder_count")

    def test_does_not_report_false_positive_for_dynamic_args(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            {"format": "%s#%s", "args": ["${inputs.repository}", "${step.issue.outputs.number}"]},
            path=("blocks", "0", "steps", "0", "publish", "issue_ref"),
            source="demo.yml",
        )

        self.assertEqual(diagnostics, [])
