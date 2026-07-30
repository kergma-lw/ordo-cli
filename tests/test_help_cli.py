import unittest

from ordo.help_cli import build_search_response


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


if __name__ == "__main__":
    unittest.main()
