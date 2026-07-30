import unittest

from ordo.connectors import get_public_connector_registry


class OperationMetadataRichnessTest(unittest.TestCase):
    def test_operation_contracts_publish_summary_tags_examples_and_maturity(self) -> None:
        registry = get_public_connector_registry()

        issue = registry.get_operation("gh.issue")
        shell_command = registry.get_operation("shell.command")
        git_commits = registry.get_operation("git.commits")
        git_tag = registry.get_operation("git.tag")
        git_tags = registry.get_operation("git.tags")
        git_branch_switch = registry.get_operation("git.branch.switch")
        git_branch_create = registry.get_operation("git.branch.create")
        git_sync_fetch = registry.get_operation("git.sync.fetch")
        git_sync_push = registry.get_operation("git.sync.push")
        git_commit_create = registry.get_operation("git.commit.create")
        runtime_profile_use = registry.get_operation("runtime.profile.use")

        self.assertIsNotNone(issue)
        self.assertIsNotNone(shell_command)
        self.assertIsNotNone(git_commits)
        self.assertIsNotNone(git_tag)
        self.assertIsNotNone(git_tags)
        self.assertIsNotNone(git_branch_switch)
        self.assertIsNotNone(git_branch_create)
        self.assertIsNotNone(git_sync_fetch)
        self.assertIsNotNone(git_sync_push)
        self.assertIsNotNone(git_commit_create)
        self.assertIsNotNone(runtime_profile_use)
        assert issue is not None
        assert shell_command is not None
        assert git_commits is not None
        assert git_tag is not None
        assert git_tags is not None
        assert git_branch_switch is not None
        assert git_branch_create is not None
        assert git_sync_fetch is not None
        assert git_sync_push is not None
        assert git_commit_create is not None
        assert runtime_profile_use is not None
        self.assertEqual(issue.summary, "Probe operation 'gh.issue'")
        self.assertEqual(issue.tags, ("gh", "probe"))
        self.assertEqual(issue.examples[0]["reference"], "gh.issue")
        self.assertEqual(issue.maturity, "stable")
        self.assertEqual(shell_command.tags, ("shell", "action"))
        self.assertIn("does not expose patch text", git_commits.summary)
        self.assertEqual(git_commits.examples[0]["reference"], "git.commits")
        self.assertEqual(git_commits.tags, ("git", "probe"))
        self.assertIn("annotated tags", git_tag.summary)
        self.assertEqual(git_tag.examples[0]["reference"], "git.tag")
        self.assertIn("peeled target object id", git_tags.summary)
        self.assertIn("not the newest tag by creation date", git_tags.summary)
        self.assertEqual(git_tags.examples[1]["inputs"]["match_kind"], "regex")
        self.assertEqual(
            git_branch_switch.invalidates_observations,
            ("git.branch", "git.branches", "git.upstream", "git.ref.*", "git.tag", "git.tags", "git.worktree", "git.worktrees", "git.state", "git.repo", "git.range", "git.commits"),
        )
        self.assertEqual(git_branch_create.invalidates_observations, ("git.branches", "git.ref.*"))
        self.assertEqual(git_sync_fetch.invalidates_observations, ("git.ref.*", "git.tag", "git.tags", "git.branches", "git.repo", "git.range", "git.commits"))
        self.assertEqual(git_sync_push.invalidates_observations, ())
        self.assertEqual(
            [item.to_contract() for item in git_sync_push.preflight_observations],
            [
                {"probe": "git.branch", "with": {}},
                {"probe": "git.upstream", "with": {}},
                {"probe": "git.range", "with": {"base": "@{upstream}", "head": "{branch}"}},
            ],
        )
        self.assertEqual(git_commit_create.invalidates_observations, ("git.ref.*", "git.tag", "git.tags", "git.worktree", "git.worktrees", "git.state", "git.range", "git.commits"))
        self.assertTrue(runtime_profile_use.deprecated)
        self.assertEqual(runtime_profile_use.replaced_by, ("workflow.step.profile_switch",))

    def test_registry_contract_exposes_richer_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()
        gh_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "gh")
        issue = next(operation for operation in gh_connector["operations"] if operation["name"] == "issue")
        git_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "git")
        git_tag = next(operation for operation in git_connector["operations"] if operation["name"] == "tag")
        git_tags = next(operation for operation in git_connector["operations"] if operation["name"] == "tags")
        git_push = next(operation for operation in git_connector["operations"] if operation["name"] == "sync.push")
        self.assertEqual(issue["summary"], "Probe operation 'gh.issue'")
        self.assertEqual(issue["tags"], ["gh", "probe"])
        self.assertEqual(issue["examples"][0]["reference"], "gh.issue")
        self.assertEqual(issue["maturity"], "stable")
        self.assertEqual(git_tag["examples"][0]["inputs"], {"name": "v1.2.3"})
        self.assertEqual(git_tags["inputs"]["match_kind"], "'glob' | 'regex' | null")
        self.assertEqual(git_push["preflight_observations"][0], {"probe": "git.branch", "with": {}})


if __name__ == "__main__":
    unittest.main()
