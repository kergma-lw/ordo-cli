import unittest

from ordo.connectors import get_public_connector_registry


class OperationMetadataRichnessTest(unittest.TestCase):
    def test_operation_contracts_publish_summary_tags_examples_and_maturity(self) -> None:
        registry = get_public_connector_registry()

        issue = registry.get_operation("gh.issue")
        shell_command = registry.get_operation("shell.command")

        self.assertIsNotNone(issue)
        self.assertIsNotNone(shell_command)
        assert issue is not None
        assert shell_command is not None
        self.assertEqual(issue.summary, "Probe operation 'gh.issue'")
        self.assertEqual(issue.tags, ("gh", "probe"))
        self.assertEqual(issue.examples[0]["reference"], "gh.issue")
        self.assertEqual(issue.maturity, "stable")
        self.assertEqual(shell_command.tags, ("shell", "action"))

    def test_registry_contract_exposes_richer_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()
        issue = next(operation for operation in contract["connectors"][1]["operations"] if operation["name"] == "issue")
        self.assertEqual(issue["summary"], "Probe operation 'gh.issue'")
        self.assertEqual(issue["tags"], ["gh", "probe"])
        self.assertEqual(issue["examples"][0]["reference"], "gh.issue")
        self.assertEqual(issue["maturity"], "stable")


if __name__ == "__main__":
    unittest.main()
