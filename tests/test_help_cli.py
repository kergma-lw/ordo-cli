import unittest

from ordo.help_cli import (
    _HelpResponseContext,
    _build_search_index,
    build_command_line_response,
    build_features_response,
    build_overview_response,
    build_search_response,
    render_search_text,
)


class HelpCliSearchTest(unittest.TestCase):
    def test_prepared_search_index_preserves_search_response(self) -> None:
        query = "inspect project item details"
        prepared = _build_search_index(context=_HelpResponseContext())

        self.assertEqual(
            build_search_response(query),
            build_search_response(query, prepared_index=prepared),
        )

    def test_search_finds_operation_by_output_field_name(self) -> None:
        payload = build_search_response("project item details")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items.details", references)

    def test_search_finds_operation_by_multiword_use_case(self) -> None:
        payload = build_search_response("inspect project item details")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items.details", references)
        self.assertEqual(references[0], "gh.project.items.details")

    def test_search_finds_operation_by_input_field_name(self) -> None:
        payload = build_search_response("inspect project items")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items", references)
        self.assertIn("gh.project.items.details", references)

    def test_search_finds_pr_operations_by_pull_request_query(self) -> None:
        payload = build_search_response("inspect existing pull request")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.pr", references)

    def test_search_finds_compose_operations_by_orchestration_query(self) -> None:
        payload = build_search_response("compose start running state")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("compose.start", references)

    def test_search_finds_compose_remove_by_materialized_runtime_query(self) -> None:
        payload = build_search_response("remove stopped compose service")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("compose.remove", references)

    def test_search_publishes_exact_keyword_matches_before_full_text_results(self) -> None:
        payload = build_search_response("if")

        self.assertEqual(payload["keywords"], [{
            "name": "if",
            "targets": [{
                "name": "if",
                "summary": "Read local optional workflow behavior.",
                "command": "ordo-help describe if --json",
            }],
        }])
        text = render_search_text(payload)
        self.assertIn("- if: ordo-help describe if", text)
        self.assertNotIn("- if: ordo-help describe if --json", text)
        self.assertEqual(payload["keywords"][0]["targets"][0]["command"], "ordo-help describe if --json")
        self.assertIn("Related matches:", text)
        self.assertIn("Use `ordo-help search if --all` to include broader matches.", text)
        self.assertNotIn("Topic matches:", text)
        self.assertTrue(payload["broader_results_available"])
        self.assertLessEqual(len(payload["related"]), 6)

        all_results = build_search_response("if", include_all=True)
        self.assertFalse(all_results["broader_results_available"])
        self.assertTrue(all_results["facts"])
        self.assertFalse(all_results["related"])
        all_text = render_search_text(all_results)
        self.assertLess(all_text.index("Exact keyword matches:"), all_text.index("Topic matches:"))

    def test_search_publishes_all_qualified_choices_for_an_ambiguous_keyword(self) -> None:
        payload = build_search_response("field")

        self.assertEqual(
            [target["name"] for target in payload["keywords"][0]["targets"]],
            ["json.field", "yaml.field"],
        )

    def test_overview_surfaces_external_failure_diagnostic_rule(self) -> None:
        payload = build_overview_response()

        self.assertIn("external cause", payload["failure_diagnostics"]["rule"])
        self.assertIn("stderr_excerpt", payload["failure_diagnostics"]["external_payload_fields"])

    def test_command_line_surfaces_external_run_failure_payload_fields(self) -> None:
        payload = build_command_line_response()

        command = payload["commands"][0]
        self.assertIn("external context", command["run_failure_surface"]["rule"])
        self.assertIn("suggested_checks", command["run_failure_surface"]["external_payload_fields"])

    def test_features_connectors_cluster_mentions_external_runtime_failures(self) -> None:
        payload = build_features_response()

        cluster = next(item for item in payload["clusters"] if item["name"] == "connectors")
        self.assertTrue(any("external tool" in text for text in cluster["appropriate_when"]))
        inspect_handles = [item["handle"] for item in cluster["inspect_next"]]
        self.assertIn("command-line.ordo-playbook", inspect_handles)


if __name__ == "__main__":
    unittest.main()
