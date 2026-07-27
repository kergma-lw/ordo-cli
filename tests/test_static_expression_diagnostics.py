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

    def test_reports_mismatch_even_when_format_object_args_are_dynamic(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            {"format": "%s#%s", "args": ["${inputs.repository}", "${step.issue.outputs.number}"]},
            path=("blocks", "0", "steps", "0", "publish", "issue_ref"),
            source="demo.yml",
        )

        self.assertEqual(len(diagnostics), 1)

    def test_does_not_report_when_format_object_placeholder_count_matches(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            {"format": "{}#{}", "args": ["repo", 7]},
            path=("blocks", "0", "steps", "0", "publish", "issue_ref"),
            source="demo.yml",
        )

        self.assertEqual(diagnostics, [])

    def test_collects_statically_known_embedded_format_mismatch(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            "${format(\"{}\", \"repo\", 7)}",
            path=("blocks", "0", "steps", "0", "value"),
            source="demo.yml",
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].code, "validation.workflow.value_expr.format.placeholder_count")

    def test_does_not_report_for_embedded_format_when_dynamic_args_still_match_count(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            "${format(\"{}#{}\", inputs.repository, 7)}",
            path=("blocks", "0", "steps", "0", "value"),
            source="demo.yml",
        )

        self.assertEqual(diagnostics, [])

    def test_does_not_report_when_embedded_format_template_is_dynamic(self) -> None:
        diagnostics = collect_static_expression_diagnostics(
            "${format(inputs.template, inputs.repository, 7)}",
            path=("blocks", "0", "steps", "0", "value"),
            source="demo.yml",
        )

        self.assertEqual(diagnostics, [])
