import unittest

from ordo.help_cli import build_command_line_response, build_features_response, build_overview_response, build_search_response


class HelpCliSearchTest(unittest.TestCase):
    def test_search_finds_operation_by_output_field_name(self) -> None:
        payload = build_search_response("label_names")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items.details", references)

    def test_search_finds_operation_by_multiword_use_case(self) -> None:
        payload = build_search_response("project items labels")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items.details", references)
        self.assertEqual(references[0], "gh.project.items.details")

    def test_search_finds_operation_by_input_field_name(self) -> None:
        payload = build_search_response("content_refs")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.project.items", references)
        self.assertIn("gh.project.items.details", references)

    def test_search_finds_pr_operations_by_pull_request_query(self) -> None:
        payload = build_search_response("pull request metadata")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("gh.pr", references)

    def test_search_finds_compose_operations_by_orchestration_query(self) -> None:
        payload = build_search_response("compose start running state")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("compose.start", references)

    def test_search_finds_compose_remove_by_materialized_runtime_query(self) -> None:
        payload = build_search_response("remove stopped compose service instance")

        references = [entry["reference"] for entry in payload["operations"]]
        self.assertIn("compose.remove", references)

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
