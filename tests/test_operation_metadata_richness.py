import unittest

from ordo.connectors import get_public_connector_registry


class OperationMetadataRichnessTest(unittest.TestCase):
    def test_operation_contracts_publish_summary_tags_examples_and_maturity(self) -> None:
        registry = get_public_connector_registry()

        issue = registry.get_operation("gh.issue")
        shell_command = registry.get_operation("shell.command")
        git_commits = registry.get_operation("git.commits")
        git_branch_switch = registry.get_operation("git.branch.switch")

        self.assertIsNotNone(issue)
        self.assertIsNotNone(shell_command)
        self.assertIsNotNone(git_commits)
        self.assertIsNotNone(git_branch_switch)
        assert issue is not None
        assert shell_command is not None
        assert git_commits is not None
        assert git_branch_switch is not None
        self.assertEqual(issue.summary, "Probe operation 'gh.issue'")
        self.assertEqual(issue.tags, ("gh", "probe"))
        self.assertEqual(issue.examples[0]["reference"], "gh.issue")
        self.assertEqual(issue.maturity, "stable")
        self.assertEqual(shell_command.tags, ("shell", "action"))
        self.assertIn("does not expose patch text", git_commits.summary)
        self.assertEqual(git_commits.examples[0]["reference"], "git.commits")
        self.assertEqual(git_commits.tags, ("git", "probe"))
        self.assertEqual(git_branch_switch.invalidates_observations, ("git.branch", "git.worktree", "git.ref.*"))

    def test_registry_contract_exposes_richer_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()
        gh_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "gh")
        issue = next(operation for operation in gh_connector["operations"] if operation["name"] == "issue")
        self.assertEqual(issue["summary"], "Probe operation 'gh.issue'")
        self.assertEqual(issue["tags"], ["gh", "probe"])
        self.assertEqual(issue["examples"][0]["reference"], "gh.issue")
        self.assertEqual(issue["maturity"], "stable")


if __name__ == "__main__":
    unittest.main()
