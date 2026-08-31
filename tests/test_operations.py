import importlib
import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe, execute_action, execute_operation
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import check_workflow
from ordo.runtime.local_expression_engine.core import LiteralNode, ReferenceNode
from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation
from ordo.connectors.registry import get_public_connector_registry
from tests.support import STANDARD_CONNECTOR_PROVIDER


class OperationTest(unittest.TestCase):
    def test_execute_operation_dispatches_probe_steps_by_kind(self) -> None:
        workflow = Workflow(version=0, workflow="demo")
        registry = get_public_connector_registry()
        resolved = ResolvedOperation(
            reference="gh.issue",
            connector_namespace="gh",
            operation=registry.get_operation("gh.issue"),
            source="public",
        )

        with patch("ordo.connectors.operations.evaluate_probe") as evaluate_probe_mock:
            evaluate_probe_mock.return_value = OperationResult(status="ok", summary="probe")
            result = execute_operation(resolved, workflow)

        self.assertEqual(result.status, "ok")
        evaluate_probe_mock.assert_called_once_with(resolved, workflow)

    def test_execute_operation_dispatches_action_steps_by_kind(self) -> None:
        workflow = Workflow(version=0, workflow="demo")
        registry = get_public_connector_registry()
        resolved = ResolvedOperation(
            reference="shell.command",
            connector_namespace="shell",
            operation=registry.get_operation("shell.command"),
            source="public",
        )

        with patch("ordo.connectors.operations.execute_action") as execute_action_mock:
            execute_action_mock.return_value = OperationResult(status="ok", summary="action")
            result = execute_operation(resolved, workflow)

        self.assertEqual(result.status, "ok")
        execute_action_mock.assert_called_once_with(resolved, workflow)

    def test_migrated_git_probe_modules_publish_through_info_hook(self) -> None:
        git_repo_module = importlib.import_module("connectors.git.probes.repo")
        git_branch_module = importlib.import_module("connectors.git.probes.branch")
        git_worktree_module = importlib.import_module("connectors.git.probes.worktree")
        git_worktrees_module = importlib.import_module("connectors.git.probes.worktrees")
        git_branches_module = importlib.import_module("connectors.git.probes.branches")
        git_stash_module = importlib.import_module("connectors.git.probes.stash")
        git_commits_module = importlib.import_module("connectors.git.probes.commits")
        git_state_module = importlib.import_module("connectors.git.probes.state")
        git_ref_module = importlib.import_module("connectors.git.probes.ref")
        git_tag_module = importlib.import_module("connectors.git.probes.tag")
        git_tags_module = importlib.import_module("connectors.git.probes.tags")
        git_upstream_module = importlib.import_module("connectors.git.probes.upstream")
        git_range_module = importlib.import_module("connectors.git.probes.range")
        repo_info = git_repo_module.info()
        branch_info = git_branch_module.info()
        worktree_info = git_worktree_module.info()
        worktrees_info = git_worktrees_module.info()
        branches_info = git_branches_module.info()
        stash_info = git_stash_module.info()
        commits_info = git_commits_module.info()
        state_info = git_state_module.info()
        ref_info = git_ref_module.info()
        tag_info = git_tag_module.info()
        tags_info = git_tags_module.info()
        upstream_info = git_upstream_module.info()
        range_info = git_range_module.info()

        self.assertEqual(repo_info.name, "repo")
        self.assertEqual(repo_info.kind, "probe")
        self.assertIs(repo_info.handler, git_repo_module.run)
        self.assertEqual(branch_info.name, "branch")
        self.assertEqual(branch_info.kind, "probe")
        self.assertIs(branch_info.handler, git_branch_module.run)
        self.assertEqual(worktree_info.name, "worktree")
        self.assertEqual(worktree_info.kind, "probe")
        self.assertIs(worktree_info.handler, git_worktree_module.run)
        self.assertEqual(worktrees_info.name, "worktrees")
        self.assertEqual(worktrees_info.kind, "probe")
        self.assertIs(worktrees_info.handler, git_worktrees_module.run)
        self.assertEqual(branches_info.name, "branches")
        self.assertEqual(branches_info.kind, "probe")
        self.assertIs(branches_info.handler, git_branches_module.run)
        self.assertEqual(stash_info.name, "stash")
        self.assertEqual(stash_info.kind, "probe")
        self.assertIs(stash_info.handler, git_stash_module.run)
        self.assertEqual(commits_info.name, "commits")
        self.assertEqual(commits_info.kind, "probe")
        self.assertIs(commits_info.handler, git_commits_module.run)
        self.assertEqual(state_info.name, "state")
        self.assertEqual(state_info.kind, "probe")
        self.assertIs(state_info.handler, git_state_module.run)
        self.assertEqual(ref_info.name, "ref")
        self.assertEqual(ref_info.kind, "probe")
        self.assertIs(ref_info.handler, git_ref_module.run)
        self.assertEqual(tag_info.name, "tag")
        self.assertEqual(tag_info.kind, "probe")
        self.assertIs(tag_info.handler, git_tag_module.run)
        self.assertEqual(tags_info.name, "tags")
        self.assertEqual(tags_info.kind, "probe")
        self.assertIs(tags_info.handler, git_tags_module.run)
        self.assertEqual(upstream_info.name, "upstream")
        self.assertEqual(upstream_info.kind, "probe")
        self.assertIs(upstream_info.handler, git_upstream_module.run)
        self.assertEqual(range_info.name, "range")
        self.assertEqual(range_info.kind, "probe")
        self.assertIs(range_info.handler, git_range_module.run)

    def test_git_bootstrap_contract_exposes_only_repository_root_context(self) -> None:
        connector = get_public_connector_registry().get_connector("git")

        self.assertIsNotNone(connector)
        self.assertEqual(connector.bootstrap.context_fields, ("repository_root",))

    def test_gh_bootstrap_contract_exposes_repository_context(self) -> None:
        connector = get_public_connector_registry().get_connector("gh")

        self.assertIsNotNone(connector)
        self.assertEqual(connector.bootstrap.context_fields, ("host", "viewer", "scopes", "repository"))

    def test_git_bootstrap_uses_connector_directory_context_for_commands(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            workflow = Workflow(version=0, workflow="demo", connector_contexts={"git": {"directory": str(directory)}})
            operation = get_public_connector_registry().get_operation("git.branch")
            resolved = ResolvedOperation("git.branch", "git", operation, "public")  # type: ignore[arg-type]

            with patch("subprocess.run") as run:
                run.side_effect = [
                    self._completed(returncode=0, stdout=f"{directory}\n", stderr=""),
                    self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                ]

                result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository_root"], str(directory))
        self.assertEqual(run.call_args_list[0].kwargs.get("cwd"), str(directory))
        self.assertEqual(run.call_args_list[1].kwargs.get("cwd"), str(directory))

    def test_git_bootstrap_rejects_unknown_connector_context_fields(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"git": {"banana": 123}})
        operation = get_public_connector_registry().get_operation("git.branch")
        resolved = ResolvedOperation("git.branch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "unknown_context_field")
        self.assertEqual(result.diagnostics[0].code, "bootstrap.git_unknown_context_field")
        self.assertEqual(result.raw["unknown_fields"], ["banana"])
        run.assert_not_called()

    def test_gh_bootstrap_rejects_unknown_connector_context_fields(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"gh": {"banana": 123}})
        operation = get_public_connector_registry().get_operation("gh.repo")
        resolved = ResolvedOperation("gh.repo", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "unknown_context_field")
        self.assertEqual(result.diagnostics[0].code, "bootstrap.gh_unknown_context_field")
        run.assert_not_called()

    def test_git_operation_contracts_no_longer_primary_own_shared_bootstrap_failures(self) -> None:
        registry = get_public_connector_registry()

        branch = registry.get_operation("git.branch")
        worktree = registry.get_operation("git.worktree")
        merge = registry.get_operation("git.integrate.merge_ff_only")

        self.assertEqual(branch.failure_modes, ("probe_failed",))
        self.assertEqual(worktree.failure_modes, ("probe_failed",))
        self.assertEqual(merge.failure_modes, ("ref_not_found", "non_fast_forward", "merge_blocked"))

        switch = registry.get_operation("git.branch.switch")
        self.assertEqual(
            switch.failure_modes,
            ("branch_not_found", "worktree_change_conflict", "unresolved_state", "switch_blocked"),
        )
        create = registry.get_operation("git.branch.create")
        self.assertEqual(
            create.failure_modes,
            ("invalid_branch", "branch_exists", "start_point_not_found", "create_blocked"),
        )
        commit_create = registry.get_operation("git.commit.create")
        self.assertEqual(
            commit_create.failure_modes,
            ("message_invalid", "nothing_to_commit", "commit_blocked"),
        )
        index_add_all = registry.get_operation("git.index.add_all")
        self.assertEqual(index_add_all.failure_modes, ("stage_blocked",))
        commit_amend = registry.get_operation("git.commit.amend")
        self.assertEqual(
            commit_amend.failure_modes,
            ("message_invalid", "nothing_to_amend", "amend_blocked"),
        )
        commit_revert = registry.get_operation("git.commit.revert")
        self.assertEqual(
            commit_revert.failure_modes,
            ("commit_not_found", "merge_commit_not_supported", "revert_conflict", "revert_blocked"),
        )
        integrate_merge = registry.get_operation("git.integrate.merge")
        self.assertEqual(
            integrate_merge.failure_modes,
            ("ref_not_found", "merge_conflict", "merge_blocked"),
        )
        integrate_merge_ff = registry.get_operation("git.integrate.merge_ff_only")
        self.assertEqual(
            integrate_merge_ff.failure_modes,
            ("ref_not_found", "non_fast_forward", "merge_blocked"),
        )
        integrate_rebase = registry.get_operation("git.integrate.rebase_onto")
        self.assertEqual(
            integrate_rebase.failure_modes,
            ("onto_not_found", "upstream_not_found", "branch_not_found", "default_branch_protected", "rebase_conflict", "rebase_blocked"),
        )
        integrate_cherry_pick = registry.get_operation("git.integrate.cherry_pick")
        self.assertEqual(
            integrate_cherry_pick.failure_modes,
            ("commit_not_found", "merge_commit_not_supported", "cherry_pick_conflict", "cherry_pick_blocked"),
        )
        sync_fetch = registry.get_operation("git.sync.fetch")
        self.assertEqual(sync_fetch.failure_modes, ("remote_not_found", "fetch_blocked"))
        sync_push = registry.get_operation("git.sync.push")
        self.assertEqual(
            sync_push.failure_modes,
            ("branch_not_found", "remote_not_found", "upstream_remote_missing", "non_fast_forward", "push_blocked"),
        )
        delete = registry.get_operation("git.branch.delete")
        self.assertEqual(
            delete.failure_modes,
            ("branch_not_found", "branch_checked_out", "default_branch_protected", "branch_not_merged", "delete_blocked"),
        )

    def test_git_initial_action_surface_replaces_previous_custom_actions(self) -> None:
        registry = get_public_connector_registry()

        expected = {
            "git.branch.switch",
            "git.branch.create",
            "git.branch.delete",
            "git.commit.create",
            "git.commit.amend",
            "git.commit.revert",
            "git.index.add_all",
            "git.integrate.merge",
            "git.integrate.merge_ff_only",
            "git.integrate.rebase_onto",
            "git.integrate.cherry_pick",
            "git.sync.fetch",
            "git.sync.push",
        }

        for reference in expected:
            self.assertIsNotNone(registry.get_operation(reference), reference)

        self.assertIsNone(registry.get_operation("git.branch_from_issue"))
        self.assertIsNone(registry.get_operation("git.merge_to_main_ff"))
        self.assertIsNone(registry.get_operation("git.sync_main_ff_only"))

    def test_gh_and_shell_operation_contracts_no_longer_primary_own_shared_bootstrap_failures(self) -> None:
        registry = get_public_connector_registry()

        gh_issue = registry.get_operation("gh.issue")
        gh_issue_comments = registry.get_operation("gh.issue.comments")
        gh_pr = registry.get_operation("gh.pr")
        gh_pr_checks = registry.get_operation("gh.pr.checks")
        gh_pr_comments = registry.get_operation("gh.pr.comments")
        gh_pr_diff = registry.get_operation("gh.pr.diff")
        gh_pr_reviews = registry.get_operation("gh.pr.reviews")
        gh_pr_review_comments = registry.get_operation("gh.pr.review_comments")
        gh_pr_timeline = registry.get_operation("gh.pr.timeline")
        gh_repo = registry.get_operation("gh.repo")
        gh_repo_sync = registry.get_operation("gh.repo.sync")
        gh_repo_actions_permissions = registry.get_operation("gh.repo.actions.permissions")
        gh_repo_actions_permissions_set = registry.get_operation("gh.repo.actions.permissions.set")
        gh_project_items = registry.get_operation("gh.project.items")
        gh_close = registry.get_operation("gh.issue.close")
        shell_command = registry.get_operation("shell.command")

        self.assertEqual(gh_issue.failure_modes, ("issue_not_found", "probe_failed"))
        self.assertEqual(gh_issue_comments.failure_modes, ("issue_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_pr.failure_modes, ("pull_not_found", "probe_failed"))
        self.assertEqual(gh_pr_checks.failure_modes, ("pull_not_found", "checks_unavailable", "probe_failed"))
        self.assertEqual(gh_pr_comments.failure_modes, ("pull_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_pr_diff.failure_modes, ("pull_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_pr_reviews.failure_modes, ("pull_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_pr_review_comments.failure_modes, ("pull_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_pr_timeline.failure_modes, ("pull_not_found", "limit_invalid", "probe_failed"))
        self.assertEqual(gh_repo.failure_modes, ("repository_not_found", "probe_failed"))
        self.assertEqual(
            gh_repo_sync.failure_modes,
            ("repository_not_found", "not_a_fork", "archived_repository", "default_branch_unavailable", "sync_blocked"),
        )
        self.assertEqual(gh_repo_actions_permissions.failure_modes, ("repository_not_found", "probe_failed"))
        self.assertEqual(gh_repo_actions_permissions_set.failure_modes, ("repository_not_found", "set_blocked"))
        self.assertEqual(
            gh_project_items.failure_modes,
            ("project_not_found", "unknown_field", "ambiguous_field", "unsupported_field_type", "invalid_filter_value", "invalid_content_ref", "probe_failed"),
        )
        self.assertEqual(gh_close.failure_modes, ("issue_not_found", "close_blocked"))
        self.assertEqual(shell_command.failure_modes, ("command_failed", "action_failed"))

    def test_gh_repo_probe_contract_publishes_repository_shape(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.repo")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["repository"], "string")
        self.assertEqual(operation.outputs["default_branch"], "string | null")
        self.assertEqual(operation.outputs["parent_repository"], "string | null")

    def test_gh_repo_probe_returns_normalized_repository_facts(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"gh": {"repository": "owner/repo"}}, guards=(Guard(OperationRef("gh.repo")),), steps=())
        operation = get_public_connector_registry().get_operation("gh.repo")
        resolved = ResolvedOperation("gh.repo", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo","isFork":true,"isArchived":false,"defaultBranchRef":{"name":"main"},"parent":{"nameWithOwner":"upstream/repo"}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["id"], "R_1")
        self.assertEqual(result.outputs["repository"], "owner/repo")
        self.assertEqual(result.outputs["default_branch"], "main")
        self.assertTrue(result.outputs["is_fork"])
        self.assertEqual(result.outputs["parent_repository"], "upstream/repo")
        self.assertFalse(result.outputs["archived"])

    def test_gh_repo_probe_reports_repository_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"gh": {"repository": "owner/missing"}}, guards=(Guard(OperationRef("gh.repo")),), steps=())
        operation = get_public_connector_registry().get_operation("gh.repo")
        resolved = ResolvedOperation("gh.repo", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="repository not found"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "repository_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_repo.repository_not_found")

    def test_gh_repo_actions_permissions_probe_returns_enabled_state(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"gh": {"repository": "owner/repo"}}, guards=(Guard(OperationRef("gh.repo.actions.permissions")),), steps=())
        operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions")
        resolved = ResolvedOperation("gh.repo.actions.permissions", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository"], "owner/repo")
        self.assertTrue(result.outputs["enabled"])
        self.assertEqual(result.outputs["allowed_actions"], "all")
        self.assertFalse(result.outputs["sha_pinning_required"])

    def test_gh_repo_actions_permissions_probe_reports_repository_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", connector_contexts={"gh": {"repository": "owner/missing"}}, guards=(Guard(OperationRef("gh.repo.actions.permissions")),), steps=())
        operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions")
        resolved = ResolvedOperation("gh.repo.actions.permissions", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="repository not found"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "repository_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_repo_actions_permissions.repository_not_found")

    def test_gh_pr_probe_contract_publishes_metadata_shape(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.pr")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["repository"], "string")
        self.assertEqual(operation.inputs["pull_number"], "integer")
        self.assertEqual(operation.outputs["head_sha"], "string")
        self.assertEqual(operation.outputs["commits_count"], "integer")

    def test_gh_pr_probe_returns_normalized_metadata(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr")
        resolved = ResolvedOperation("gh.pr", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"number":42,"title":"Add PR probes","body":"Body","state":"open","draft":false,"html_url":"https://github.com/kergma-lw/ordo-cli/pull/42","created_at":"2026-07-30T10:00:00Z","updated_at":"2026-07-30T11:00:00Z","user":{"login":"kergma-lw"},"base":{"ref":"main"},"head":{"ref":"feature/pr-probes","sha":"abc123"},"mergeable":true,"mergeable_state":"clean","review_decision":"APPROVED","additions":12,"deletions":3,"changed_files":2,"commits":4}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository"], "kergma-lw/ordo-cli")
        self.assertEqual(result.outputs["number"], 42)
        self.assertEqual(result.outputs["author"]["login"], "kergma-lw")
        self.assertEqual(result.outputs["head_sha"], "abc123")
        self.assertEqual(result.outputs["commits_count"], 4)

    def test_gh_pr_diff_probe_contract_publishes_summary_shape(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.pr.diff")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["repository"], "string")
        self.assertEqual(operation.inputs["pull_number"], "integer")
        self.assertEqual(operation.inputs["limit"], "integer")
        self.assertEqual(operation.outputs["pull_ref"], "string")
        self.assertEqual(operation.outputs["total_files"], "integer")
        self.assertEqual(operation.outputs["files"][0], "object")

    def test_gh_pr_diff_probe_returns_normalized_file_summaries(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"filename":"src/ordo/help_cli.py","status":"modified","additions":12,"deletions":3,"changes":15},{"filename":"site-docs/operations/gh/pr-diff.md","status":"added","additions":24,"deletions":0,"changes":24}]',
                    stderr="",
                ),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["pull_ref"], "kergma-lw/ordo-cli#42")
        self.assertEqual(result.outputs["total_files"], 2)
        self.assertEqual(result.outputs["files"][0]["path"], "src/ordo/help_cli.py")
        self.assertEqual(result.outputs["files"][0]["status"], "modified")
        self.assertEqual(result.outputs["files"][0]["changes"], 15)
        self.assertTrue(result.outputs["files"][0]["truncated"])
        self.assertFalse(result.outputs["files"][0]["binary"])
        self.assertEqual(result.outputs["files"][1]["status"], "added")

    def test_gh_pr_diff_probe_reports_invalid_limit(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42, "limit": 0})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "limit_invalid")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_diff.invalid_limit")

    def test_gh_pr_diff_probe_reports_missing_pull_request(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 999})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="gh: Not Found (HTTP 404)\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "pull_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_diff.not_found")

    def test_gh_pr_diff_probe_returns_patch_and_rename_metadata(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"filename":"docs/reminders.md","previous_filename":"docs/notifications.md","status":"renamed","additions":4,"deletions":2,"changes":6}]',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='diff --git a/docs/notifications.md b/docs/reminders.md\nindex 1111111..2222222 100644\n--- a/docs/notifications.md\n+++ b/docs/reminders.md\n@@ -1,2 +1,4 @@\n-old\n+new\n+more\n',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["files"][0]["previous_path"], "docs/notifications.md")
        self.assertEqual(result.outputs["files"][0]["patch"], "@@ -1,2 +1,4 @@\n-old\n+new\n+more")
        self.assertFalse(result.outputs["files"][0]["truncated"])
        self.assertFalse(result.outputs["files"][0]["binary"])

    def test_gh_pr_diff_probe_marks_binary_files_explicitly(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"filename":"assets/logo.png","status":"modified","additions":0,"deletions":0,"changes":0}]',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='diff --git a/assets/logo.png b/assets/logo.png\nindex 1111111..2222222 100644\nBinary files a/assets/logo.png and b/assets/logo.png differ\n',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.outputs["files"][0]["patch"])
        self.assertFalse(result.outputs["files"][0]["truncated"])
        self.assertTrue(result.outputs["files"][0]["binary"])

    def test_gh_pr_diff_probe_bounds_large_patch_content(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.diff", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.diff")
        resolved = ResolvedOperation("gh.pr.diff", "gh", operation, "public")  # type: ignore[arg-type]
        long_patch = "@@ -1 +1 @@\n" + ("+x\n" * 2500)

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"filename":"src/ordo/help_cli.py","status":"modified","additions":2500,"deletions":1,"changes":2501,"patch":"' + long_patch.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"}]',
                    stderr="",
                ),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["files"][0]["truncated"])
        self.assertFalse(result.outputs["files"][0]["binary"])
        self.assertLessEqual(len(result.outputs["files"][0]["patch"]), 4000)

    def test_gh_pr_checks_probe_returns_normalized_statuses_and_check_runs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.checks", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.checks")
        resolved = ResolvedOperation("gh.pr.checks", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":42,"head":{"sha":"abc123"}}', stderr=""),
                self._completed(returncode=0, stdout='{"state":"pending","statuses":[{"context":"lint","state":"success","target_url":"https://example.test/lint"},{"context":"deploy","state":"pending","target_url":"https://example.test/deploy"}]}', stderr=""),
                self._completed(returncode=0, stdout='{"total_count":2,"check_runs":[{"name":"unit","status":"completed","conclusion":"success","html_url":"https://example.test/unit"},{"name":"release","status":"completed","conclusion":"skipped","html_url":"https://example.test/release"}]}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["head_sha"], "abc123")
        self.assertEqual(result.outputs["total_count"], 4)
        self.assertEqual(result.outputs["success_count"], 2)
        self.assertEqual(result.outputs["pending_count"], 1)
        self.assertEqual(result.outputs["skipped_count"], 1)
        self.assertEqual(result.outputs["failed_count"], 0)
        self.assertEqual(result.outputs["overall_state"], "pending")
        self.assertEqual(result.outputs["checks"][0]["kind"], "status")
        self.assertEqual(result.outputs["checks"][2]["kind"], "check_run")

    def test_gh_pr_checks_probe_reports_unavailable_checks(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.checks", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.checks")
        resolved = ResolvedOperation("gh.pr.checks", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":42,"head":{"sha":"abc123"}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="api rate limit exceeded\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.statuses_failed")

    def test_gh_pr_probe_reports_missing_pull_request(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 999})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr")
        resolved = ResolvedOperation("gh.pr", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="gh: Not Found (HTTP 404)\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "pull_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr.not_found")

    def test_gh_pr_comments_probe_returns_structured_comment_nodes(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.comments", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.comments")
        resolved = ResolvedOperation("gh.pr.comments", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":42,"comments":2}', stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"id":1,"body":"First","created_at":"2026-07-30T10:00:00Z","updated_at":"2026-07-30T10:00:00Z","html_url":"https://github.com/kergma-lw/ordo-cli/pull/42#issuecomment-1","user":{"login":"kergma-lw"}},{"id":2,"body":"Second","created_at":"2026-07-30T11:00:00Z","updated_at":"2026-07-30T11:00:00Z","html_url":"https://github.com/kergma-lw/ordo-cli/pull/42#issuecomment-2","user":{"login":"ww"}}]',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["pull_ref"], "kergma-lw/ordo-cli#42")
        self.assertEqual(result.outputs["total_count"], 2)
        self.assertEqual(result.outputs["comments"][0]["author"]["login"], "kergma-lw")

    def test_gh_pr_reviews_probe_returns_structured_reviews(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.reviews", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.reviews")
        resolved = ResolvedOperation("gh.pr.reviews", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"pullRequest":{"reviews":{"totalCount":1,"nodes":[{"id":"PRR_1","url":"https://github.com/kergma-lw/ordo-cli/pull/42#pullrequestreview-1","body":"Looks good","state":"APPROVED","submittedAt":"2026-07-30T12:00:00Z","author":{"login":"ww"},"commit":{"oid":"abc123"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["total_count"], 1)
        self.assertEqual(result.outputs["reviews"][0]["state"], "APPROVED")
        self.assertEqual(result.outputs["reviews"][0]["commit_id"], "abc123")

    def test_gh_pr_timeline_probe_returns_normalized_supported_events(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.timeline", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.timeline")
        resolved = ResolvedOperation("gh.pr.timeline", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":42,"state":"open"}', stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"event":"ready_for_review","created_at":"2026-07-30T10:00:00Z","actor":{"login":"kergma-lw"}},{"event":"review_requested","created_at":"2026-07-30T11:00:00Z","actor":{"login":"kergma-lw"},"requested_reviewer":{"login":"ww"}},{"event":"base_ref_changed","created_at":"2026-07-30T12:00:00Z","actor":{"login":"kergma-lw"},"previous_ref":"develop","current_ref":"main"},{"event":"commented","created_at":"2026-07-30T12:30:00Z","actor":{"login":"bot"}}]',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["total_count"], 3)
        self.assertEqual(result.outputs["events"][0]["event_type"], "ready_for_review")
        self.assertEqual(result.outputs["events"][1]["payload"]["requested_reviewer"], "ww")
        self.assertEqual(result.outputs["events"][2]["from_value"], "develop")
        self.assertEqual(result.outputs["events"][2]["to_value"], "main")

    def test_gh_pr_review_comments_probe_returns_structured_line_comments(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.pr.review_comments", with_={"repository": "kergma-lw/ordo-cli", "pull_number": 42})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.pr.review_comments")
        resolved = ResolvedOperation("gh.pr.review_comments", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":42,"review_comments":1}', stderr=""),
                self._completed(
                    returncode=0,
                    stdout='[{"id":10,"body":"Please rename this","path":"src/ordo/help_cli.py","commit_id":"def456","original_commit_id":"abc123","line":12,"original_line":12,"side":"RIGHT","in_reply_to_id":null,"created_at":"2026-07-30T13:00:00Z","updated_at":"2026-07-30T13:00:00Z","html_url":"https://github.com/kergma-lw/ordo-cli/pull/42#discussion_r10","user":{"login":"reviewer"}}]',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["total_count"], 1)
        self.assertEqual(result.outputs["comments"][0]["path"], "src/ordo/help_cli.py")
        self.assertEqual(result.outputs["comments"][0]["author"]["login"], "reviewer")

    def test_gh_project_items_probe_contract_publishes_normalized_collection_shape(self) -> None:
        registry = get_public_connector_registry()

        gh_project_items = registry.get_operation("gh.project.items")

        self.assertIsNotNone(gh_project_items)
        self.assertEqual(gh_project_items.kind, "probe")
        self.assertEqual(gh_project_items.inputs["project_id"], "string")
        self.assertEqual(gh_project_items.inputs["content_kind"], "string")
        self.assertEqual(gh_project_items.inputs["filters"][0]["field"], "string")
        self.assertEqual(gh_project_items.inputs["content_refs"][0], "string")
        self.assertEqual(gh_project_items.outputs["count"], "integer")
        self.assertEqual(gh_project_items.outputs["items"][0]["content_kind"], "string")

    def test_gh_project_items_probe_returns_normalized_items(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_issue","content":{"__typename":"Issue","number":7,"title":"Implement items probe","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[]}}, {"id":"PVTI_draft","content":{"__typename":"DraftIssue"},"fieldValues":{"nodes":[]}}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_issue")
        self.assertEqual(result.outputs["items"][0]["content_kind"], "Issue")
        self.assertEqual(result.outputs["items"][0]["repository"], "owner/repo")
        self.assertEqual(result.outputs["items"][0]["number"], 7)
        self.assertEqual(result.outputs["items"][1]["item_id"], "PVTI_draft")
        self.assertEqual(result.outputs["items"][1]["content_kind"], "DraftIssue")
        self.assertIsNone(result.outputs["items"][1]["repository"])
        self.assertIsNone(result.outputs["items"][1]["number"])

    def test_gh_project_items_probe_paginates_without_per_item_followup_fetches(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":true,"endCursor":"CURSOR_1"},"nodes":[{"id":"PVTI_1","content":{"__typename":"Issue","number":1,"title":"First","url":"https://github.com/owner/repo/issues/1","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[]}}]}}}}',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_2","content":{"__typename":"PullRequest","number":2,"title":"Second","url":"https://github.com/owner/repo/pull/2","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[]}}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(len(result.outputs["items"]), 2)
        self.assertEqual(run.call_count, 3)
        first_query = run.call_args_list[1].args[0]
        second_query = run.call_args_list[2].args[0]
        self.assertNotIn("fieldValues", first_query)
        self.assertIn("after=CURSOR_1", second_query)

    def test_gh_project_items_probe_reports_missing_project(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_missing"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.project_not_found")

    def test_gh_project_items_probe_filters_by_content_kind(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "content_kind": "Issue"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_issue","content":{"__typename":"Issue","number":7,"title":"Issue","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[]}}, {"id":"PVTI_pr","content":{"__typename":"PullRequest","number":8,"title":"PR","url":"https://github.com/owner/repo/pull/8","repository":{"nameWithOwner":"owner/repo"}},"fieldValues":{"nodes":[]}}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["content_kind"], "Issue")
        self.assertIn("search=is:issue", run.call_args_list[1].args[0])

    def test_gh_project_items_probe_applies_multiple_field_filters_with_and_semantics(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "gh.project.items",
                        with_={
                            "project_id": "PVT_demo",
                            "filters": [
                                {"field": "Status", "value": "Ready"},
                                {"field": "Estimate", "value": 3},
                            ],
                        },
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status","name":"Status","options":[{"id":"O_ready","name":"Ready"}]},{"__typename":"ProjectV2Field","id":"F_estimate","name":"Estimate","dataType":"NUMBER"}]}}}}',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_match","content":{"__typename":"Issue","number":7,"title":"Match","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"}}}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_match")
        self.assertIn("search=Status:Ready Estimate:3", run.call_args_list[2].args[0])

    def test_gh_project_items_probe_reports_unknown_field(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "filters": [{"field": "Size", "value": "M"}] })),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "unknown_field")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.unknown_field")

    def test_gh_project_items_probe_reports_ambiguous_field(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "filters": [{"field": "Status", "value": "Ready"}] })),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status_1","name":"Status","options":[]},{"__typename":"ProjectV2SingleSelectField","id":"F_status_2","name":"Status","options":[]}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ambiguous_field")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.ambiguous_field")

    def test_gh_project_items_probe_reports_unsupported_field_type(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "filters": [{"field": "Repository", "value": "owner/repo"}] })),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2Field","id":"F_repo","name":"Repository","dataType":"REPOSITORY"}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "unsupported_field_type")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.unsupported_field_type")

    def test_gh_project_items_probe_reports_invalid_filter_value(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "filters": [{"field": "Estimate", "value": "three"}] })),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2Field","id":"F_estimate","name":"Estimate","dataType":"NUMBER"}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "invalid_filter_value")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.invalid_filter_value")

    def test_gh_project_items_probe_intersects_explicit_content_refs_without_project_scan(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "gh.project.items",
                        with_={"project_id": "PVT_demo", "content_refs": ["owner/repo#7", "owner/repo#8"]},
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repo_0":{"issue_0":{"__typename":"Issue","number":7,"title":"Issue 7","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"projectItems":{"nodes":[{"id":"PVTI_issue","project":{"id":"PVT_demo"}}]}}},"repo_1":{"pull_1":{"__typename":"PullRequest","number":8,"title":"PR 8","url":"https://github.com/owner/repo/pull/8","repository":{"nameWithOwner":"owner/repo"},"projectItems":{"nodes":[{"id":"PVTI_pr","project":{"id":"PVT_demo"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_issue")
        self.assertEqual(result.outputs["items"][1]["item_id"], "PVTI_pr")
        self.assertEqual(run.call_count, 2)
        query = " ".join(run.call_args_list[1].args[0])
        self.assertIn("issue_0:issue(number:7)", query)
        self.assertIn("pull_1:pullRequest(number:8)", query)
        self.assertNotIn("items(first:100,after:$after", query)

    def test_gh_project_items_probe_applies_filters_with_content_refs_subset_mode(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "gh.project.items",
                        with_={
                            "project_id": "PVT_demo",
                            "content_kind": "Issue",
                            "content_refs": ["owner/repo#7", "owner/repo#8"],
                            "filters": [{"field": "Status", "value": "Ready"}],
                        },
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status","name":"Status","options":[{"id":"O_ready","name":"Ready"}]}]}}}}',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repo_0":{"issue_0":{"__typename":"Issue","number":7,"title":"Issue 7","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"projectItems":{"nodes":[{"id":"PVTI_issue","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready"}}]}}},"repo_1":{"issue_1":{"__typename":"Issue","number":8,"title":"Issue 8","url":"https://github.com/owner/repo/issues/8","repository":{"nameWithOwner":"owner/repo"},"projectItems":{"nodes":[{"id":"PVTI_issue_8","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Backlog"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_issue")
        query = " ".join(run.call_args_list[2].args[0])
        self.assertIn("field_0:fieldValueByName(name:\"Status\")", query)
        self.assertIn("issue_0:issue(number:7)", query)
        self.assertNotIn("pull_0:pullRequest", query)

    def test_gh_project_items_probe_reports_invalid_content_ref(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "content_refs": ["owner/repo"]})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "invalid_content_ref")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_items.invalid_content_ref")

    def test_gh_project_items_details_probe_contract_publishes_detail_shape(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.project.items.details")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["project_id"], "string")
        self.assertEqual(operation.inputs["content_refs"][0], "string")
        self.assertEqual(operation.outputs["items"][0]["state"], "string")
        self.assertEqual(operation.outputs["items"][0]["label_names"][0], "string")
        self.assertEqual(
            operation.failure_modes,
            ("project_not_found", "unknown_field", "ambiguous_field", "unsupported_field_type", "invalid_filter_value", "invalid_content_ref", "probe_failed"),
        )

    def test_gh_project_items_details_probe_returns_labels_and_state(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.items.details", with_={"project_id": "PVT_demo"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.items.details")
        resolved = ResolvedOperation("gh.project.items.details", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"items":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"PVTI_issue","content":{"__typename":"Issue","number":7,"title":"Implement items probe","state":"OPEN","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[{"name":"bug"},{"name":"type:task"}]}}}, {"id":"PVTI_draft","content":{"__typename":"DraftIssue"}}]}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["items"][0]["state"], "OPEN")
        self.assertEqual(result.outputs["items"][0]["label_names"], ["bug", "type:task"])
        self.assertIsNone(result.outputs["items"][1]["state"])
        self.assertIsNone(result.outputs["items"][1]["label_names"])

    def test_gh_project_items_details_probe_uses_content_refs_batch_path(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items.details", with_={"project_id": "PVT_demo", "content_refs": ["owner/repo#7"]})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items.details")
        resolved = ResolvedOperation("gh.project.items.details", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repo_0":{"issue_0":{"__typename":"Issue","number":7,"title":"Issue 7","state":"OPEN","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[{"name":"type:task"}]},"projectItems":{"nodes":[{"id":"PVTI_issue","project":{"id":"PVT_demo"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["label_names"], ["type:task"])
        query = " ".join(run.call_args_list[1].args[0])
        self.assertIn("labels(first:100){nodes{name}}", query)
        self.assertIn("state", query)

    def test_gh_project_items_details_probe_applies_filters_in_subset_mode(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "gh.project.items.details",
                        with_={
                            "project_id": "PVT_demo",
                            "content_kind": "Issue",
                            "filters": [{"field": "Status", "value": "Ready"}],
                            "content_refs": ["owner/repo#7", "owner/repo#8"],
                        },
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items.details")
        resolved = ResolvedOperation("gh.project.items.details", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_status","name":"Status","options":[{"id":"O_ready","name":"Ready"}]}]}}}}',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repo_0":{"issue_0":{"__typename":"Issue","number":7,"title":"Issue 7","state":"OPEN","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[{"name":"type:task"}]},"projectItems":{"nodes":[{"id":"PVTI_issue","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Ready"}}]}}},"repo_1":{"issue_1":{"__typename":"Issue","number":8,"title":"Issue 8","state":"OPEN","url":"https://github.com/owner/repo/issues/8","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[]},"projectItems":{"nodes":[{"id":"PVTI_issue_8","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"Backlog"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_issue")

    def test_gh_project_items_details_probe_combines_content_and_project_filters_in_subset_mode(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "gh.project.items.details",
                        with_={
                            "project_id": "PVT_demo",
                            "content_kind": "Issue",
                            "filters": [
                                {"field": "State", "value": "OPEN"},
                                {"field": "Priority", "value": "P1"},
                            ],
                            "content_refs": ["owner/repo#7", "owner/repo#8", "owner/repo#9"],
                        },
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items.details")
        resolved = ResolvedOperation("gh.project.items.details", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"node":{"id":"PVT_demo","title":"Demo","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F_priority","name":"Priority","options":[{"id":"O_p1","name":"P1"},{"id":"O_p2","name":"P2"}]}]}}}}',
                    stderr="",
                ),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repo_0":{"issue_0":{"__typename":"Issue","number":7,"title":"Issue 7","state":"OPEN","url":"https://github.com/owner/repo/issues/7","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[]},"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"P1"}}]}}},"repo_1":{"issue_1":{"__typename":"Issue","number":8,"title":"Issue 8","state":"CLOSED","url":"https://github.com/owner/repo/issues/8","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[]},"projectItems":{"nodes":[{"id":"PVTI_8","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"P1"}}]}}},"repo_2":{"issue_2":{"__typename":"Issue","number":9,"title":"Issue 9","state":"OPEN","url":"https://github.com/owner/repo/issues/9","repository":{"nameWithOwner":"owner/repo"},"labels":{"nodes":[]},"projectItems":{"nodes":[{"id":"PVTI_9","project":{"id":"PVT_demo"},"field_0":{"__typename":"ProjectV2ItemFieldSingleSelectValue","name":"P2"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 1)
        self.assertEqual(result.outputs["items"][0]["item_id"], "PVTI_7")

    def test_gh_issue_comments_probe_returns_structured_comment_nodes(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue.comments", with_={"repository": "kergma-lw/ordo-cli", "issue_number": 471})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue.comments")
        resolved = ResolvedOperation("gh.issue.comments", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"issue":{"comments":{"totalCount":2,"nodes":[{"id":"IC_1","url":"https://github.com/kergma-lw/ordo-cli/issues/471#issuecomment-1","body":"First","createdAt":"2026-07-27T10:00:00Z","updatedAt":"2026-07-27T10:00:00Z","author":{"login":"kergma-lw"}},{"id":"IC_2","url":"https://github.com/kergma-lw/ordo-cli/issues/471#issuecomment-2","body":"Second","createdAt":"2026-07-27T11:00:00Z","updatedAt":"2026-07-27T11:00:00Z","author":{"login":"ww"}}]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "kergma-lw/ordo-cli#471")
        self.assertEqual(result.outputs["total_count"], 2)
        self.assertEqual(len(result.outputs["comments"]), 2)
        self.assertEqual(result.outputs["comments"][0]["body"], "First")

    def test_gh_issue_comments_probe_rejects_invalid_limit(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue.comments", with_={"repository": "kergma-lw/ordo-cli", "issue_number": 471, "limit": 0})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue.comments")
        resolved = ResolvedOperation("gh.issue.comments", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "limit_invalid")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_issue_comments.invalid_limit")

    def test_gh_issue_comments_probe_accepts_large_limit(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue.comments", with_={"repository": "kergma-lw/ordo-cli", "issue_number": 471, "limit": 250})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue.comments")
        resolved = ResolvedOperation("gh.issue.comments", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"issue":{"comments":{"totalCount":0,"nodes":[]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["total_count"], 0)

    def test_git_worktree_returns_structured_probe_outputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.worktree")),), steps=())
        operation = get_public_connector_registry().get_operation("git.worktree")
        resolved = ResolvedOperation("git.worktree", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout=" M README.md\n?? tmp.txt\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["clean"])
        self.assertEqual(result.outputs["dirty_paths"], ["README.md", "tmp.txt"])
        self.assertTrue(result.outputs["has_untracked"])
        self.assertFalse(result.outputs["has_staged_changes"])
        self.assertTrue(result.outputs["has_unstaged_changes"])
        self.assertEqual(result.outputs["repository_root"], "/tmp/demo-repo")

    def test_git_worktree_probe_reports_staged_and_untracked_state(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.worktree")),), steps=())
        operation = get_public_connector_registry().get_operation("git.worktree")
        resolved = ResolvedOperation("git.worktree", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="A  staged.txt\n M unstaged.txt\n?? tmp.txt\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["clean"])
        self.assertEqual(result.outputs["dirty_paths"], ["staged.txt", "unstaged.txt", "tmp.txt"])
        self.assertTrue(result.outputs["has_untracked"])
        self.assertTrue(result.outputs["has_staged_changes"])
        self.assertTrue(result.outputs["has_unstaged_changes"])

    def test_git_worktree_probe_fails_on_unexpected_status_shape(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.worktree")),), steps=())
        operation = get_public_connector_registry().get_operation("git.worktree")
        resolved = ResolvedOperation("git.worktree", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="Mbad\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_worktree.invalid_status_line")

    def test_git_worktrees_probe_returns_worktree_inventory(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.worktrees")),), steps=())
        operation = get_public_connector_registry().get_operation("git.worktrees")
        resolved = ResolvedOperation("git.worktrees", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "worktree /tmp/demo-repo\n"
                        "HEAD 1111111111111111111111111111111111111111\n"
                        "branch refs/heads/feature/demo\n"
                        "\n"
                        "worktree /tmp/demo-repo-linked\n"
                        "HEAD 2222222222222222222222222222222222222222\n"
                        "detached true\n"
                        "\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["current_path"], "/tmp/demo-repo")
        self.assertEqual(
            result.outputs["items"],
            [
                {
                    "path": "/tmp/demo-repo",
                    "head": "1111111111111111111111111111111111111111",
                    "branch": "feature/demo",
                    "bare": False,
                    "current": True,
                    "detached": False,
                },
                {
                    "path": "/tmp/demo-repo-linked",
                    "head": "2222222222222222222222222222222222222222",
                    "branch": None,
                    "bare": False,
                    "current": False,
                    "detached": True,
                },
            ],
        )

    def test_git_worktrees_probe_fails_on_unexpected_branch_ref(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.worktrees")),), steps=())
        operation = get_public_connector_registry().get_operation("git.worktrees")
        resolved = ResolvedOperation("git.worktrees", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "worktree /tmp/demo-repo\n"
                        "HEAD 1111111111111111111111111111111111111111\n"
                        "branch main\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_worktrees.invalid_branch_ref")

    def test_git_branches_probe_returns_local_and_remote_inventory(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branches")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branches")
        resolved = ResolvedOperation("git.branches", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "*\trefs/heads/feature/demo\tfeature/demo\n"
                        " \trefs/heads/main\tmain\n"
                        " \trefs/remotes/origin/feature/demo\torigin/feature/demo\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 3)
        self.assertEqual(result.outputs["current"], "feature/demo")
        self.assertEqual(
            result.outputs["items"],
            [
                {
                    "name": "feature/demo",
                    "ref": "refs/heads/feature/demo",
                    "kind": "local",
                    "current": True,
                },
                {
                    "name": "main",
                    "ref": "refs/heads/main",
                    "kind": "local",
                    "current": False,
                },
                {
                    "name": "origin/feature/demo",
                    "ref": "refs/remotes/origin/feature/demo",
                    "kind": "remote",
                    "current": False,
                },
            ],
        )

    def test_git_branches_probe_allows_no_current_branch_in_detached_head(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branches")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branches")
        resolved = ResolvedOperation("git.branches", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout=" \trefs/heads/main\tmain\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.outputs["current"])

    def test_git_branches_probe_fails_on_unsupported_ref_kind(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branches")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branches")
        resolved = ResolvedOperation("git.branches", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout=" \trefs/tags/v1\tv1\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_branches.invalid_ref_kind")

    def test_git_stash_probe_returns_stash_inventory(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.stash")),), steps=())
        operation = get_public_connector_registry().get_operation("git.stash")
        resolved = ResolvedOperation("git.stash", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "stash@{0}: WIP on feature/demo: abc1234 update docs\n"
                        "stash@{1}: On main: save scratch work\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(
            result.outputs["items"],
            [
                {
                    "name": "stash@{0}",
                    "selector": "stash@{0}",
                    "summary": "WIP on feature/demo: abc1234 update docs",
                },
                {
                    "name": "stash@{1}",
                    "selector": "stash@{1}",
                    "summary": "On main: save scratch work",
                },
            ],
        )

    def test_git_stash_probe_fails_on_invalid_line_shape(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.stash")),), steps=())
        operation = get_public_connector_registry().get_operation("git.stash")
        resolved = ResolvedOperation("git.stash", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="stash@{0} WIP missing separator\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_stash.invalid_line")

    def test_git_state_probe_returns_aggregate_repository_state(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.state")),), steps=())
        operation = get_public_connector_registry().get_operation("git.state")
        resolved = ResolvedOperation("git.state", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout=" M README.md\n?? tmp.txt\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="stash@{0}: WIP on feature/demo: abc1234 save work\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "branch": "feature/demo",
                "detached": False,
                "repository_root": "/tmp/demo-repo",
                "worktree_clean": False,
                "has_untracked": True,
                "has_staged_changes": False,
                "has_unstaged_changes": True,
                "stash_count": 1,
            },
        )

    def test_git_state_probe_surfaces_dependency_failure(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.state")),), steps=())
        operation = get_public_connector_registry().get_operation("git.state")
        resolved = ResolvedOperation("git.state", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="HEAD\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_branch.invalid_ref")

    def test_git_commits_probe_returns_bounded_readable_commit_entries(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.commits", with_={"limit": 2, "rev": "HEAD"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.commits")
        resolved = ResolvedOperation("git.commits", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "1111111111111111111111111111111111111111\x1fAlice\x1f2026-07-09T12:00:00+00:00\x1fAdd parser\x1fHandle edge cases\n\x1e"
                        "2222222222222222222222222222222222222222\x1fBob\x1f2026-07-08T08:30:00+00:00\x1fRefine docs\x1f\x1e"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["rev"], "HEAD")
        self.assertEqual(result.outputs["repository_root"], "/tmp/demo-repo")
        self.assertEqual(result.outputs["items"][0]["commit"], "1111111111111111111111111111111111111111")
        self.assertEqual(result.outputs["items"][0]["text"], "Add parser\n\nHandle edge cases")
        self.assertEqual(result.outputs["items"][1]["body"], "")
        self.assertEqual(result.outputs["items"][1]["text"], "Refine docs")

    def test_git_commits_probe_rejects_non_positive_limit(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.commits", with_={"limit": 0, "rev": "HEAD"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.commits")
        resolved = ResolvedOperation("git.commits", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr="")]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_commits.invalid_limit")

    def test_git_commits_probe_reports_unresolved_revision_scope(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.commits", with_={"limit": 2, "rev": "missing"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.commits")
        resolved = ResolvedOperation("git.commits", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="fatal: ambiguous argument 'missing'\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_commits.unresolved_rev")

    def test_git_ref_probe_returns_existing_symbolic_ref_facts(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.ref", with_={"ref": "HEAD"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.ref")
        resolved = ResolvedOperation("git.ref", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "name": "HEAD",
                "exists": True,
                "oid": "1111111111111111111111111111111111111111",
                "symbolic": True,
                "symbolic_target": "refs/heads/feature/demo",
                "repository_root": "/tmp/demo-repo",
            },
        )

    def test_git_ref_probe_returns_missing_ref_as_exists_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.ref", with_={"ref": "refs/heads/missing"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.ref")
        resolved = ResolvedOperation("git.ref", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["name"], "refs/heads/missing")
        self.assertFalse(result.outputs["exists"])
        self.assertIsNone(result.outputs["oid"])
        self.assertFalse(result.outputs["symbolic"])
        self.assertIsNone(result.outputs["symbolic_target"])

    def test_git_ref_probe_fails_on_empty_symbolic_target(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.ref", with_={"ref": "HEAD"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.ref")
        resolved = ResolvedOperation("git.ref", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=0, stdout="\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_ref.empty_symbolic_target")

    def test_git_tag_probe_returns_existing_tag_facts(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.tag", with_={"name": "v1.2.3"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tag")
        resolved = ResolvedOperation("git.tag", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="2222222222222222222222222222222222222222\n", stderr=""),
                self._completed(returncode=0, stdout="tag\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "name": "v1.2.3",
                "ref": "refs/tags/v1.2.3",
                "exists": True,
                "oid": "2222222222222222222222222222222222222222",
                "annotated": True,
                "repository_root": "/tmp/demo-repo",
            },
        )

    def test_git_tag_probe_returns_missing_tag_as_exists_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.tag", with_={"name": "v9.9.9"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tag")
        resolved = ResolvedOperation("git.tag", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["name"], "v9.9.9")
        self.assertEqual(result.outputs["ref"], "refs/tags/v9.9.9")
        self.assertFalse(result.outputs["exists"])
        self.assertIsNone(result.outputs["oid"])
        self.assertIsNone(result.outputs["annotated"])

    def test_git_tags_probe_returns_filtered_inventory_and_latest(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.tags", with_={"match": "v1.*"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tags")
        resolved = ResolvedOperation("git.tags", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "refs/tags/v2.0.0\tv2.0.0\tcommit\t3333333333333333333333333333333333333333\t\n"
                        "refs/tags/v1.10.0\tv1.10.0\tcommit\t2222222222222222222222222222222222222222\t\n"
                        "refs/tags/v1.2.0\tv1.2.0\ttag\taaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\t1111111111111111111111111111111111111111\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual(result.outputs["repository_root"], "/tmp/demo-repo")
        self.assertEqual(
            result.outputs["items"],
            [
                {
                    "name": "v1.10.0",
                    "ref": "refs/tags/v1.10.0",
                    "oid": "2222222222222222222222222222222222222222",
                    "annotated": False,
                },
                {
                    "name": "v1.2.0",
                    "ref": "refs/tags/v1.2.0",
                    "oid": "1111111111111111111111111111111111111111",
                    "annotated": True,
                },
            ],
        )
        self.assertEqual(result.outputs["latest"], result.outputs["items"][0])

    def test_git_tags_probe_supports_regex_match_kind(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(
                Guard(
                    OperationRef(
                        "git.tags",
                        with_={"match": r"^v?[0-9]+\.[0-9]+\.[0-9]+$", "match_kind": "regex"},
                    )
                ),
            ),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tags")
        resolved = ResolvedOperation("git.tags", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        "refs/tags/v2.0.0\tv2.0.0\tcommit\t3333333333333333333333333333333333333333\t\n"
                        "refs/tags/release-2026-07\trelease-2026-07\tcommit\t2222222222222222222222222222222222222222\t\n"
                        "refs/tags/1.4.1\t1.4.1\tcommit\t1111111111111111111111111111111111111111\t\n"
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["count"], 2)
        self.assertEqual([item["name"] for item in result.outputs["items"]], ["v2.0.0", "1.4.1"])

    def test_git_tags_probe_uses_literal_tab_delimiters_in_git_format(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.tags")),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tags")
        resolved = ResolvedOperation("git.tags", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout="refs/tags/v1.0.0\tv1.0.0\ttag\taaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\t1111111111111111111111111111111111111111\n",
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        query = run.call_args_list[1].args[0]
        format_arg = next(arg for arg in query if isinstance(arg, str) and arg.startswith("--format="))
        self.assertIn("\t", format_arg)
        self.assertNotIn("%x09", format_arg)

    def test_git_tags_probe_rejects_invalid_regex(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.tags", with_={"match": "(", "match_kind": "regex"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.tags")
        resolved = ResolvedOperation("git.tags", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr="")]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_tags.invalid_match")

    def test_git_upstream_probe_returns_tracking_facts(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.upstream")),), steps=())
        operation = get_public_connector_registry().get_operation("git.upstream")
        resolved = ResolvedOperation("git.upstream", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/feature/demo\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "configured": True,
                "branch": "feature/demo",
                "upstream_ref": "origin/feature/demo",
                "remote": "origin",
                "remote_branch": "feature/demo",
                "repository_root": "/tmp/demo-repo",
            },
        )

    def test_git_upstream_probe_returns_unconfigured_for_detached_head(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.upstream")),), steps=())
        operation = get_public_connector_registry().get_operation("git.upstream")
        resolved = ResolvedOperation("git.upstream", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="detached\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["configured"])
        self.assertIsNone(result.outputs["branch"])
        self.assertIsNone(result.outputs["upstream_ref"])

    def test_git_upstream_probe_returns_unconfigured_without_tracking_branch(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.upstream")),), steps=())
        operation = get_public_connector_registry().get_operation("git.upstream")
        resolved = ResolvedOperation("git.upstream", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="no upstream configured\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["configured"])
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertIsNone(result.outputs["upstream_ref"])

    def test_git_upstream_probe_fails_on_invalid_upstream_shape(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.upstream")),), steps=())
        operation = get_public_connector_registry().get_operation("git.upstream")
        resolved = ResolvedOperation("git.upstream", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_upstream.invalid_ref")

    def test_git_range_probe_returns_range_facts(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.range", with_={"base": "main", "head": "feature/demo"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.range")
        resolved = ResolvedOperation("git.range", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=0, stdout="2222222222222222222222222222222222222222\n", stderr=""),
                self._completed(returncode=0, stdout="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", stderr=""),
                self._completed(returncode=0, stdout="3 5\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "base": "main",
                "head": "feature/demo",
                "base_oid": "1111111111111111111111111111111111111111",
                "head_oid": "2222222222222222222222222222222222222222",
                "merge_base_oid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "ahead_count": 5,
                "behind_count": 3,
                "repository_root": "/tmp/demo-repo",
            },
        )

    def test_git_range_probe_allows_missing_merge_base(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.range", with_={"base": "main", "head": "feature/demo"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.range")
        resolved = ResolvedOperation("git.range", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=0, stdout="2222222222222222222222222222222222222222\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="no merge base\n"),
                self._completed(returncode=0, stdout="0 7\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.outputs["merge_base_oid"])
        self.assertEqual(result.outputs["ahead_count"], 7)
        self.assertEqual(result.outputs["behind_count"], 0)

    def test_git_range_probe_fails_when_ref_cannot_be_resolved(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.range", with_={"base": "main", "head": "missing"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.range")
        resolved = ResolvedOperation("git.range", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_range.unresolved_ref")

    def test_git_range_probe_fails_on_invalid_count_shape(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("git.range", with_={"base": "main", "head": "feature/demo"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("git.range")
        resolved = ResolvedOperation("git.range", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="1111111111111111111111111111111111111111\n", stderr=""),
                self._completed(returncode=0, stdout="2222222222222222222222222222222222222222\n", stderr=""),
                self._completed(returncode=0, stdout="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", stderr=""),
                self._completed(returncode=0, stdout="oops\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_range.invalid_counts")

    def test_git_branch_expression_can_block_main_branch(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(expr='git.branch.value != "main"'),), steps=())

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "git.branch":
                return OperationResult(status="ok", outputs={"value": "main"})
            return OperationResult(status="ok")

        result = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)

    def test_shell_command_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="run", operation=OperationRef("shell.command", with_={"command": "echo hi"})),),
        )
        operation = get_public_connector_registry().get_operation("shell.command")
        resolved = ResolvedOperation("shell.command", "shell", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-shell\n", stderr=""),
                self._completed(returncode=0, stdout="hi\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.raw["stdout"], "hi\n")
        self.assertEqual(result.outputs["exit_code"], 0)

    def test_shell_command_surfaces_external_failure_details(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="run", operation=OperationRef("shell.command", with_={"command": "./script.sh"})),),
        )
        operation = get_public_connector_registry().get_operation("shell.command")
        resolved = ResolvedOperation("shell.command", "shell", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-shell\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "command_failed")
        self.assertEqual(result.diagnostics[0].details["classification"], "permission_denied")
        self.assertEqual(result.diagnostics[0].details["external_tool"], "bash")

    def test_git_branch_switch_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="switch", operation=OperationRef("git.branch.switch", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.switch")
        resolved = ResolvedOperation("git.branch.switch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertTrue(result.outputs["changed"])

    def test_git_branch_switch_reports_successful_noop_when_branch_already_current(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="switch", operation=OperationRef("git.branch.switch", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.switch")
        resolved = ResolvedOperation("git.branch.switch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="Already on 'feature/demo'\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertFalse(result.outputs["changed"])

    def test_git_branch_switch_distinguishes_worktree_conflict(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="switch", operation=OperationRef("git.branch.switch", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.switch")
        resolved = ResolvedOperation("git.branch.switch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(
                    returncode=1,
                    stdout="",
                    stderr="error: Your local changes to the following files would be overwritten by checkout:\n README.md\n",
                ),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "worktree_change_conflict")

    def test_git_branch_switch_distinguishes_unresolved_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="switch", operation=OperationRef("git.branch.switch", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.switch")
        resolved = ResolvedOperation("git.branch.switch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: you need to resolve your current index first\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "unresolved_state")

    def test_git_commit_create_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="commit", operation=OperationRef("git.commit.create", with_={"message": "Add demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.create")
        resolved = ResolvedOperation("git.commit.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="[feature/demo abc1234] Add demo\n 1 file changed\n", stderr=""),
                self._completed(returncode=0, stdout="abc1234567890\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.outputs["commit"], "abc1234567890")

    def test_git_commit_create_rejects_blank_message(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="commit", operation=OperationRef("git.commit.create", with_={"message": "   "})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.create")
        resolved = ResolvedOperation("git.commit.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
            ]
            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "message_invalid")
        self.assertEqual(run.call_count, 1)

    def test_git_commit_create_distinguishes_nothing_to_commit(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="commit", operation=OperationRef("git.commit.create", with_={"message": "Add demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.create")
        resolved = ResolvedOperation("git.commit.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="nothing to commit, working tree clean\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "nothing_to_commit")

    def test_git_index_add_all_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="stage", operation=OperationRef("git.index.add_all")),),
        )
        operation = get_public_connector_registry().get_operation("git.index.add_all")
        resolved = ResolvedOperation("git.index.add_all", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["staged"], True)

    def test_git_index_add_all_reports_stage_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="stage", operation=OperationRef("git.index.add_all")),),
        )
        operation = get_public_connector_registry().get_operation("git.index.add_all")
        resolved = ResolvedOperation("git.index.add_all", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: could not stage\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "stage_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.git.index_add_all_blocked")

    def test_git_commit_amend_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="amend", operation=OperationRef("git.commit.amend", with_={"message": "Refine demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.amend")
        resolved = ResolvedOperation("git.commit.amend", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="abc111\n", stderr=""),
                self._completed(returncode=0, stdout="[feature/demo def5678] Refine demo\n 1 file changed\n", stderr=""),
                self._completed(returncode=0, stdout="def5678901234\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.outputs["previous_commit"], "abc111")
        self.assertEqual(result.outputs["commit"], "def5678901234")

    def test_git_commit_amend_supports_preserving_message(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="amend", operation=OperationRef("git.commit.amend")),))
        operation = get_public_connector_registry().get_operation("git.commit.amend")
        resolved = ResolvedOperation("git.commit.amend", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="abc111\n", stderr=""),
                self._completed(returncode=0, stdout="[feature/demo def5678] Existing title\n 1 file changed\n", stderr=""),
                self._completed(returncode=0, stdout="def5678901234\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["previous_commit"], "abc111")
        self.assertEqual(result.outputs["commit"], "def5678901234")

    def test_git_commit_amend_rejects_blank_message(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="amend", operation=OperationRef("git.commit.amend", with_={"message": "  "})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.amend")
        resolved = ResolvedOperation("git.commit.amend", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "message_invalid")

    def test_git_commit_amend_distinguishes_nothing_to_amend(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="amend", operation=OperationRef("git.commit.amend", with_={"message": "Refine demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.amend")
        resolved = ResolvedOperation("git.commit.amend", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "nothing_to_amend")

    def test_git_commit_revert_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="revert", operation=OperationRef("git.commit.revert", with_={"commit": "abc123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.revert")
        resolved = ResolvedOperation("git.commit.revert", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="abc123\n", stderr=""),
                self._completed(returncode=0, stdout="[feature/demo def5678] Revert \"Add demo\"\n 1 file changed\n", stderr=""),
                self._completed(returncode=0, stdout="def5678901234\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["reverted_commit"], "abc123")
        self.assertEqual(result.outputs["revert_commit"], "def5678901234")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_commit_revert_distinguishes_merge_commit_not_supported(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="revert", operation=OperationRef("git.commit.revert", with_={"commit": "merge123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.revert")
        resolved = ResolvedOperation("git.commit.revert", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="merge123\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: commit merge123 is a merge but no -m option was given\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "merge_commit_not_supported")

    def test_git_commit_revert_distinguishes_revert_conflict(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="revert", operation=OperationRef("git.commit.revert", with_={"commit": "abc123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.commit.revert")
        resolved = ResolvedOperation("git.commit.revert", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="abc123\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: could not revert abc123\nhint: after resolving the conflicts, mark the corrected paths\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "revert_conflict")

    def test_git_integrate_merge_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge", with_={"ref": "main"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge")
        resolved = ResolvedOperation("git.integrate.merge", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=0, stdout="Merge made by the 'ort' strategy.\n", stderr=""),
                self._completed(returncode=0, stdout="mergedhead\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["merged_ref"], "mainsha")
        self.assertEqual(result.outputs["head_commit"], "mergedhead")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_integrate_merge_distinguishes_missing_ref(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge", with_={"ref": "missing"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge")
        resolved = ResolvedOperation("git.integrate.merge", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ref_not_found")

    def test_git_integrate_merge_distinguishes_merge_conflict(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge", with_={"ref": "main"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge")
        resolved = ResolvedOperation("git.integrate.merge", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="Automatic merge failed; fix conflicts and then commit the result.\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "merge_conflict")

    def test_git_integrate_merge_ff_only_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge_ff_only", with_={"ref": "main"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge_ff_only")
        resolved = ResolvedOperation("git.integrate.merge_ff_only", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=0, stdout="Updating abc..def\nFast-forward\n", stderr=""),
                self._completed(returncode=0, stdout="mergedhead\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["merged_ref"], "mainsha")
        self.assertEqual(result.outputs["head_commit"], "mergedhead")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_integrate_merge_ff_only_distinguishes_missing_ref(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge_ff_only", with_={"ref": "missing"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge_ff_only")
        resolved = ResolvedOperation("git.integrate.merge_ff_only", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ref_not_found")

    def test_git_integrate_merge_ff_only_distinguishes_non_fast_forward(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="merge", operation=OperationRef("git.integrate.merge_ff_only", with_={"ref": "main"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.merge_ff_only")
        resolved = ResolvedOperation("git.integrate.merge_ff_only", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Not possible to fast-forward, aborting.\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "non_fast_forward")

    def test_git_integrate_rebase_onto_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="rebase",
                    operation=OperationRef("git.integrate.rebase_onto", with_={"onto": "main", "upstream": "origin/main", "branch": "feature/demo"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.rebase_onto")
        resolved = ResolvedOperation("git.integrate.rebase_onto", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=0, stdout="upstreamsha\n", stderr=""),
                self._completed(returncode=0, stdout="branchsha\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
                self._completed(returncode=0, stdout="Successfully rebased and updated refs/heads/feature/demo.\n", stderr=""),
                self._completed(returncode=0, stdout="rebasedhead\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.outputs["onto"], "mainsha")
        self.assertEqual(result.outputs["head_commit"], "rebasedhead")

    def test_git_integrate_rebase_onto_distinguishes_missing_onto(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="rebase",
                    operation=OperationRef("git.integrate.rebase_onto", with_={"onto": "missing", "upstream": "origin/main", "branch": "feature/demo"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.rebase_onto")
        resolved = ResolvedOperation("git.integrate.rebase_onto", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "onto_not_found")

    def test_git_integrate_rebase_onto_protects_default_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="rebase",
                    operation=OperationRef("git.integrate.rebase_onto", with_={"onto": "main", "upstream": "origin/main", "branch": "main"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.rebase_onto")
        resolved = ResolvedOperation("git.integrate.rebase_onto", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=0, stdout="upstreamsha\n", stderr=""),
                self._completed(returncode=0, stdout="mainbranchsha\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "default_branch_protected")

    def test_git_integrate_rebase_onto_distinguishes_rebase_conflict(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="rebase",
                    operation=OperationRef("git.integrate.rebase_onto", with_={"onto": "main", "upstream": "origin/main", "branch": "feature/demo"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.rebase_onto")
        resolved = ResolvedOperation("git.integrate.rebase_onto", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="mainsha\n", stderr=""),
                self._completed(returncode=0, stdout="upstreamsha\n", stderr=""),
                self._completed(returncode=0, stdout="branchsha\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: could not apply abc123\nhint: Resolve all conflicts manually\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "rebase_conflict")

    def test_git_integrate_cherry_pick_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="pick", operation=OperationRef("git.integrate.cherry_pick", with_={"commit": "abc123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.cherry_pick")
        resolved = ResolvedOperation("git.integrate.cherry_pick", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="abc123\n", stderr=""),
                self._completed(returncode=0, stdout="[main def5678] Add demo\n 1 file changed\n", stderr=""),
                self._completed(returncode=0, stdout="def5678901234\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["picked_commit"], "abc123")
        self.assertEqual(result.outputs["head_commit"], "def5678901234")
        self.assertEqual(result.outputs["branch"], "main")

    def test_git_integrate_cherry_pick_distinguishes_merge_commit_not_supported(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="pick", operation=OperationRef("git.integrate.cherry_pick", with_={"commit": "merge123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.cherry_pick")
        resolved = ResolvedOperation("git.integrate.cherry_pick", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="merge123\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: commit merge123 is a merge but no -m option was given\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "merge_commit_not_supported")

    def test_git_integrate_cherry_pick_distinguishes_conflict(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="pick", operation=OperationRef("git.integrate.cherry_pick", with_={"commit": "abc123"})),),
        )
        operation = get_public_connector_registry().get_operation("git.integrate.cherry_pick")
        resolved = ResolvedOperation("git.integrate.cherry_pick", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="abc123\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: could not apply abc123\nhint: after resolving the conflicts, mark the corrected paths\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "cherry_pick_conflict")

    def test_git_sync_fetch_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="fetch", operation=OperationRef("git.sync.fetch", with_={"remote": "origin"})),),
        )
        operation = get_public_connector_registry().get_operation("git.sync.fetch")
        resolved = ResolvedOperation("git.sync.fetch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "origin")
        self.assertTrue(result.outputs["fetched"])

    def test_git_sync_fetch_distinguishes_missing_remote(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="fetch", operation=OperationRef("git.sync.fetch", with_={"remote": "missing"})),),
        )
        operation = get_public_connector_registry().get_operation("git.sync.fetch")
        resolved = ResolvedOperation("git.sync.fetch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: 'missing' does not appear to be a git repository\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "remote_not_found")

    def test_git_sync_push_returns_structured_action_result_with_explicit_remote(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="push", operation=OperationRef("git.sync.push", with_={"branch": "feature/demo", "remote": "origin"})),),
        )
        operation = get_public_connector_registry().get_operation("git.sync.push")
        resolved = ResolvedOperation("git.sync.push", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "origin")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_sync_push_uses_upstream_remote_when_remote_omitted(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="push", operation=OperationRef("git.sync.push", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.sync.push")
        resolved = ResolvedOperation("git.sync.push", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "origin")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_sync_push_reports_missing_upstream_remote(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="push", operation=OperationRef("git.sync.push", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.sync.push")
        resolved = ResolvedOperation("git.sync.push", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=128, stdout="", stderr="fatal: no upstream configured\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "upstream_remote_missing")

    def test_git_branch_create_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("git.branch.create", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.create")
        resolved = ResolvedOperation("git.branch.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=1, stdout="", stderr=""),
                self._completed(returncode=0, stdout="abc1234567890\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.outputs["start_point"], "abc1234567890")

    def test_git_branch_create_supports_explicit_start_point(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="create",
                    operation=OperationRef("git.branch.create", with_={"branch": "feature/demo", "start_point": "main"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.branch.create")
        resolved = ResolvedOperation("git.branch.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=1, stdout="", stderr=""),
                self._completed(returncode=0, stdout="feedface12345678\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.outputs["start_point"], "feedface12345678")

    def test_git_branch_create_distinguishes_existing_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("git.branch.create", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.create")
        resolved = ResolvedOperation("git.branch.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "branch_exists")

    def test_git_branch_create_distinguishes_missing_start_point(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(
                Step(
                    name="create",
                    operation=OperationRef("git.branch.create", with_={"branch": "feature/demo", "start_point": "missing"}),
                ),
            ),
        )
        operation = get_public_connector_registry().get_operation("git.branch.create")
        resolved = ResolvedOperation("git.branch.create", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=1, stdout="", stderr=""),
                self._completed(returncode=1, stdout="", stderr="fatal: Needed a single revision\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "start_point_not_found")

    def test_git_branch_delete_returns_structured_action_result(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="delete", operation=OperationRef("git.branch.delete", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.delete")
        resolved = ResolvedOperation("git.branch.delete", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="main\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
                self._completed(returncode=0, stdout="Deleted branch feature/demo (was abc1234).\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["branch"], "feature/demo")

    def test_git_branch_delete_protects_default_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="delete", operation=OperationRef("git.branch.delete", with_={"branch": "main"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.delete")
        resolved = ResolvedOperation("git.branch.delete", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "default_branch_protected")

    def test_git_branch_delete_distinguishes_checked_out_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="delete", operation=OperationRef("git.branch.delete", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.delete")
        resolved = ResolvedOperation("git.branch.delete", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "branch_checked_out")

    def test_git_branch_delete_distinguishes_not_merged_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="delete", operation=OperationRef("git.branch.delete", with_={"branch": "feature/demo"})),),
        )
        operation = get_public_connector_registry().get_operation("git.branch.delete")
        resolved = ResolvedOperation("git.branch.delete", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/main\n", stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="main\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="error: The branch 'feature/demo' is not fully merged.\n"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "branch_not_merged")

    def test_gh_issue_returns_structured_probe_data(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 1})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"nameWithOwner":"owner/repo","issue":{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":{"nodes":[]},"assignees":{"nodes":[]},"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"stateReason":null,"projectItems":{"nodes":[]}}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["number"], 1)
        self.assertEqual(result.outputs["created_at"], "2026-01-01T00:00:00Z")

    def test_gh_issue_accepts_repository_and_issue_number_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 1})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"nameWithOwner":"owner/repo","issue":{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":{"nodes":[]},"assignees":{"nodes":[]},"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"stateReason":null,"projectItems":{"nodes":[]}}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["number"], 1)

    def test_gh_probe_surfaces_bootstrap_failure_before_operation_logic(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 1})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=1, stdout="", stderr="not logged in"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "auth_missing")
        self.assertEqual(run.call_count, 1)

    def test_shell_action_surfaces_bootstrap_failure_before_command_logic(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="run", operation=OperationRef("shell.command", with_={"command": "echo hi"})),),
        )
        operation = get_public_connector_registry().get_operation("shell.command")
        resolved = ResolvedOperation("shell.command", "shell", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=127, stdout="", stderr="bash missing"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "shell_unavailable")
        self.assertEqual(run.call_count, 1)

    def test_gh_issue_close_closes_open_issue(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),))
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"state":"OPEN","url":"https://github.com/owner/repo/issues/7"}', stderr=""),
                self._completed(returncode=0, stdout="✓ Closed issue owner/repo#7\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#7")
        self.assertEqual(result.outputs["state"], "CLOSED")
        self.assertTrue(result.outputs["closed"])
        self.assertEqual(run.call_count, 3)

    def test_gh_issue_close_allows_explicit_repository_override_over_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "fork/repo"}},
            guards=(),
            steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"state":"OPEN","url":"https://github.com/owner/repo/issues/7"}', stderr=""),
                self._completed(returncode=0, stdout="✓ Closed issue owner/repo#7\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#7")
        self.assertFalse(any(diagnostic.code.endswith("repository_conflict") for diagnostic in result.diagnostics))

    def test_gh_issue_close_accepts_repository_and_issue_number_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"state":"OPEN","url":"https://github.com/owner/repo/issues/7"}', stderr=""),
                self._completed(returncode=0, stdout="✓ Closed issue owner/repo#7\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#7")

    def test_gh_issue_close_is_noop_for_closed_issue(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),))
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"state":"CLOSED","url":"https://github.com/owner/repo/issues/7"}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.summary, "GitHub issue is already closed")
        self.assertTrue(result.outputs["closed"])
        self.assertEqual(run.call_count, 2)

    def test_gh_issue_close_reports_issue_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),))
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_close.issue_not_found")

    def test_gh_issue_close_reports_close_blocked(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"repository": "owner/repo", "issue_number": 7})),))
        operation = get_public_connector_registry().get_operation("gh.issue.close")
        resolved = ResolvedOperation("gh.issue.close", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"state":"OPEN","url":"https://github.com/owner/repo/issues/7"}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "close_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_close.command_failed")
        self.assertEqual(result.diagnostics[0].details["classification"], "permission_denied")
        self.assertEqual(result.diagnostics[0].details["external_tool"], "gh")

    def test_gh_issue_create_creates_issue(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/repo", "title": "Add checklist", "body": "Need a checklist."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo"}}}', stderr=""),
                self._completed(returncode=0, stdout='https://github.com/owner/repo/issues/17\n', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#17")
        self.assertEqual(result.outputs["repository"], "owner/repo")
        self.assertEqual(result.outputs["number"], 17)
        self.assertEqual(result.outputs["title"], "Add checklist")

    def test_gh_issue_create_reports_repository_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/missing", "title": "Add checklist"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="repository not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "repository_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_create.repository_not_found")

    def test_gh_issue_create_reports_title_invalid(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/repo", "title": "   "})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "title_invalid")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_create.title_invalid")

    def test_gh_issue_create_reports_create_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/repo", "title": "Add checklist"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo"}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "create_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_create.command_failed")

    def test_gh_issue_create_reports_rate_limit_details(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/repo", "title": "Add checklist"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo"}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="api rate limit exceeded"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "create_blocked")
        self.assertEqual(result.diagnostics[0].details["classification"], "rate_limited")
        self.assertEqual(result.diagnostics[0].details["external_system"], "github")

    def test_gh_issue_create_reports_missing_issue_url(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="create", operation=OperationRef("gh.issue.create", with_={"repository": "owner/repo", "title": "Add checklist"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.create")
        resolved = ResolvedOperation("gh.issue.create", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo"}}}', stderr=""),
                self._completed(returncode=0, stdout='created\n', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "create_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_create.missing_fields")

    def test_gh_repo_sync_syncs_default_branch(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="sync", operation=OperationRef("gh.repo.sync")),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.sync")
        resolved = ResolvedOperation("gh.repo.sync", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo","isFork":true,"isArchived":false,"defaultBranchRef":{"name":"main"},"parent":{"nameWithOwner":"upstream/repo"}}}}',
                    stderr="",
                ),
                self._completed(returncode=0, stdout="synced\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository"], "owner/repo")
        self.assertEqual(result.outputs["branch"], "main")
        self.assertEqual(result.outputs["upstream_repository"], "upstream/repo")
        self.assertTrue(result.outputs["synced"])

    def test_gh_repo_sync_reports_not_a_fork(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="sync", operation=OperationRef("gh.repo.sync")),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.sync")
        resolved = ResolvedOperation("gh.repo.sync", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo","isFork":false,"isArchived":false,"defaultBranchRef":{"name":"main"},"parent":null}}}',
                    stderr="",
                ),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "not_a_fork")
        self.assertEqual(result.diagnostics[0].code, "action.gh_repo_sync.not_a_fork")

    def test_gh_repo_sync_reports_default_branch_unavailable(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="sync", operation=OperationRef("gh.repo.sync")),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.sync")
        resolved = ResolvedOperation("gh.repo.sync", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"id":"R_1","nameWithOwner":"owner/repo","isFork":true,"isArchived":false,"defaultBranchRef":null,"parent":{"nameWithOwner":"upstream/repo"}}}}',
                    stderr="",
                ),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "default_branch_unavailable")
        self.assertEqual(result.diagnostics[0].code, "action.gh_repo_sync.default_branch_unavailable")

    def test_gh_repo_actions_permissions_set_updates_enabled_state(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="set", operation=OperationRef("gh.repo.actions.permissions.set", with_={"enabled": False})),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions.set")
        resolved = ResolvedOperation("gh.repo.actions.permissions.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}', stderr=""),
                self._completed(returncode=0, stdout="", stderr=""),
                self._completed(returncode=0, stdout='{"enabled":false,"allowed_actions":"all","sha_pinning_required":false}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository"], "owner/repo")
        self.assertFalse(result.outputs["enabled"])
        self.assertTrue(result.outputs["changed"])

    def test_gh_repo_actions_permissions_set_is_noop_when_already_matching(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="set", operation=OperationRef("gh.repo.actions.permissions.set", with_={"enabled": True})),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions.set")
        resolved = ResolvedOperation("gh.repo.actions.permissions.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertTrue(result.outputs["enabled"])

    def test_gh_repo_actions_permissions_set_reports_set_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "owner/repo"}},
            guards=(),
            steps=(Step(name="set", operation=OperationRef("gh.repo.actions.permissions.set", with_={"enabled": False})),),
        )
        operation = get_public_connector_registry().get_operation("gh.repo.actions.permissions.set")
        resolved = ResolvedOperation("gh.repo.actions.permissions.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "set_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_repo_actions_permissions_set.command_failed")

    def test_gh_issue_comment_add_creates_comment(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"repository": "owner/repo", "issue_number": 17, "body": "Looks good."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.comment.add")
        resolved = ResolvedOperation("gh.issue.comment.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"id":"I_17","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=0, stdout="commented\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"comments":{"nodes":[{"id":"IC_1","url":"https://github.com/owner/repo/issues/17#issuecomment-1","body":"Looks good."}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#17")
        self.assertEqual(result.outputs["comment_id"], "IC_1")
        self.assertEqual(result.outputs["body"], "Looks good.")

    def test_gh_issue_comment_add_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"repository": "owner/repo", "issue_number": 999, "body": "Looks good."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.comment.add")
        resolved = ResolvedOperation("gh.issue.comment.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_comment_add.issue_not_found")

    def test_gh_issue_comment_add_reports_body_invalid(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"repository": "owner/repo", "issue_number": 17, "body": "   "})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.comment.add")
        resolved = ResolvedOperation("gh.issue.comment.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "body_invalid")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_comment_add.body_invalid")

    def test_gh_issue_comment_add_reports_comment_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"repository": "owner/repo", "issue_number": 17, "body": "Looks good."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.comment.add")
        resolved = ResolvedOperation("gh.issue.comment.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"id":"I_17","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "comment_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_comment_add.command_failed")

    def test_gh_issue_comment_add_reports_unknown_external_failure_details(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"repository": "owner/repo", "issue_number": 17, "body": "Looks good."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.comment.add")
        resolved = ResolvedOperation("gh.issue.comment.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"id":"I_17","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="boom"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "comment_blocked")
        self.assertEqual(result.diagnostics[0].details["classification"], "unknown_external")

    def test_gh_issue_body_replace_updates_body(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"repository": "owner/repo", "issue_number": 17, "body": "Updated body."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.replace")
        resolved = ResolvedOperation("gh.issue.body.replace", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"Old body.","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=0, stdout="edited\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#17")
        self.assertEqual(result.outputs["body"], "Updated body.")
        self.assertTrue(result.outputs["changed"])

    def test_gh_issue_body_replace_is_noop_for_same_body(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"repository": "owner/repo", "issue_number": 17, "body": "Same body."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.replace")
        resolved = ResolvedOperation("gh.issue.body.replace", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"Same body.","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub issue body is already set")

    def test_gh_issue_body_replace_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"repository": "owner/repo", "issue_number": 999, "body": "Updated body."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.replace")
        resolved = ResolvedOperation("gh.issue.body.replace", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_body_replace.issue_not_found")

    def test_gh_issue_body_replace_reports_replace_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"repository": "owner/repo", "issue_number": 17, "body": "Updated body."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.replace")
        resolved = ResolvedOperation("gh.issue.body.replace", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"Old body.","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "replace_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_body_replace.command_failed")

    def test_gh_issue_body_append_appends_with_default_separator(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"repository": "owner/repo", "issue_number": 17, "text": "New section."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.append")
        resolved = ResolvedOperation("gh.issue.body.append", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"Old body.","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=0, stdout="edited\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["body"], "Old body.\n\nNew section.")
        self.assertTrue(result.outputs["changed"])

    def test_gh_issue_body_append_uses_custom_separator(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"repository": "owner/repo", "issue_number": 17, "text": "tail", "separator": ""})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.append")
        resolved = ResolvedOperation("gh.issue.body.append", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"head","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=0, stdout="edited\n", stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["body"], "headtail")

    def test_gh_issue_body_append_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"repository": "owner/repo", "issue_number": 999, "text": "New section."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.append")
        resolved = ResolvedOperation("gh.issue.body.append", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_body_append.issue_not_found")

    def test_gh_issue_body_append_reports_text_invalid(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"repository": "owner/repo", "issue_number": 17, "text": "   "})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.append")
        resolved = ResolvedOperation("gh.issue.body.append", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "text_invalid")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_body_append.text_invalid")

    def test_gh_issue_body_append_reports_append_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"repository": "owner/repo", "issue_number": 17, "text": "New section."})),),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.body.append")
        resolved = ResolvedOperation("gh.issue.body.append", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"body":"Old body.","url":"https://github.com/owner/repo/issues/17"}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "append_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_issue_body_append.command_failed")

    def test_gh_project_issue_add_creates_project_item(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.add")
        resolved = ResolvedOperation("gh.project.issue.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"id":"I_7","projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists"}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"addProjectV2ItemById":{"item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["issue_ref"], "owner/repo#7")
        self.assertEqual(result.outputs["project_id"], "PVT_demo")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertTrue(result.outputs["added"])

    def test_gh_project_issue_add_is_noop_for_existing_project_item(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.add")
        resolved = ResolvedOperation("gh.project.issue.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"id":"I_7","projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.summary, "GitHub issue is already in the requested project")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertFalse(result.outputs["added"])

    def test_gh_project_issue_add_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.add")
        resolved = ResolvedOperation("gh.project.issue.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"id":"I_7","projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_add.project_not_found")

    def test_gh_project_issue_add_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.add")
        resolved = ResolvedOperation("gh.project.issue.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_add.issue_not_found")

    def test_gh_project_issue_add_reports_add_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.add")
        resolved = ResolvedOperation("gh.project.issue.add", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"id":"I_7","projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists"}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "add_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_add.command_failed")

    def test_gh_project_items_probe_reports_network_failure_details(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.items", with_={"project_id": "PVT_demo", "content_kind": "Issue"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.items")
        resolved = ResolvedOperation("gh.project.items", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="could not resolve host: api.github.com"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].details["classification"], "network_failed")
        self.assertEqual(result.diagnostics[0].details["external_tool"], "gh")

    def test_gh_project_issue_status_set_updates_project_status(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Status", "option": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"},{"id":"OPT_2","name":"In progress"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["option"], "In progress")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_status_set_is_noop_for_same_status(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Status", "option": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"In progress","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"},{"id":"OPT_2","name":"In progress"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Status' is already set")

    def test_gh_project_issue_status_set_reports_option_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Status", "option": "Done"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "option_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.option_not_found")

    def test_gh_project_issue_status_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Status", "option": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.project_not_found")

    def test_gh_project_issue_status_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Status", "option": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.issue_not_found")

    def test_gh_project_issue_status_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Status", "option": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"},{"id":"OPT_2","name":"In progress"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.command_failed")

    def test_gh_project_issue_iteration_set_updates_project_iteration(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14},{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["iteration"], "Sprint 12")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_iteration_set_is_noop_for_same_iteration(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 12","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Iteration' is already set")

    def test_gh_project_issue_iteration_set_reports_iteration_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 13"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14}]}}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "iteration_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_iteration_set.iteration_not_found")

    def test_gh_project_issue_iteration_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_iteration_set.project_not_found")

    def test_gh_project_issue_iteration_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_iteration_set.issue_not_found")

    def test_gh_project_issue_iteration_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14},{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_iteration_set.command_failed")

    def test_gh_project_issue_priority_set_updates_priority(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["option"], "P1")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_priority_set_is_noop_for_same_priority(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P1","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Priority' is already set")

    def test_gh_project_issue_priority_set_reports_option_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Priority", "option": "P0"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "option_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.option_not_found")

    def test_gh_project_issue_priority_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.project_not_found")

    def test_gh_project_issue_priority_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.issue_not_found")

    def test_gh_project_issue_priority_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.command_failed")

    def test_gh_project_issue_type_set_updates_type(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Type", "option": "Bug"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["option"], "Bug")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_type_set_is_noop_for_same_type(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Type", "option": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Type' is already set")

    def test_gh_project_issue_type_set_reports_option_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Type", "option": "Story"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "option_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.option_not_found")

    def test_gh_project_issue_type_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Type", "option": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.project_not_found")

    def test_gh_project_issue_type_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Type", "option": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.issue_not_found")

    def test_gh_project_issue_type_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Type", "option": "Bug"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.command_failed")

    def test_gh_project_issue_size_set_updates_size(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Size", "option": "L"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["option"], "L")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_size_set_membership_query_is_graphql_complete(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Size", "option": "L"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        membership_argv = run.call_args_list[1].args[0]
        query_arg = membership_argv[membership_argv.index("-f") + 1]
        self.assertIn("query=", query_arg)
        self.assertTrue(query_arg.endswith("}}}}"))
        mutation_argv = run.call_args_list[3].args[0]
        mutation_arg = mutation_argv[mutation_argv.index("-f") + 1]
        self.assertTrue(mutation_arg.startswith("query=mutation("))

    def test_gh_project_issue_size_set_is_noop_for_same_size(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Size", "option": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Size' is already set")

    def test_gh_project_issue_size_set_reports_option_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Size", "option": "XL"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "option_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.option_not_found")

    def test_gh_project_issue_size_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Size", "option": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.project_not_found")

    def test_gh_project_issue_size_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Size", "option": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.issue_not_found")

    def test_gh_project_issue_size_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Size", "option": "L"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_single_select_set.command_failed")

    def test_gh_project_issue_estimate_set_updates_estimate(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Estimate", "value": 5})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["value"], 5)
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_estimate_set_is_noop_for_same_estimate(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Estimate", "value": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["changed"])
        self.assertEqual(result.summary, "GitHub project field 'Estimate' is already set")

    def test_gh_project_issue_estimate_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_missing", "field": "Estimate", "value": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_number_set.project_not_found")

    def test_gh_project_issue_estimate_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 999, "project_id": "PVT_demo", "field": "Estimate", "value": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_number_set.issue_not_found")

    def test_gh_project_issue_estimate_set_reports_field_value_invalid_for_bad_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Estimate", "value": True})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_value_invalid")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_number_set.field_value_invalid")

    def test_gh_project_issue_field_single_select_set_updates_single_select_field(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-field", operation=OperationRef("gh.project.issue.field_single_select.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Priority", "option": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_single_select.set")
        resolved = ResolvedOperation("gh.project.issue.field_single_select.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]},{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["field"], "Priority")
        self.assertEqual(result.outputs["option"], "P1")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_field_number_set_updates_number_field(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-field", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Estimate", "value": 5})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["field"], "Estimate")
        self.assertEqual(result.outputs["value"], 5)
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_field_iteration_set_updates_iteration_field(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-field", operation=OperationRef("gh.project.issue.field_iteration.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Iteration", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_iteration.set")
        resolved = ResolvedOperation("gh.project.issue.field_iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14},{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["item_id"], "PVTI_7")
        self.assertEqual(result.outputs["iteration"], "Sprint 12")
        self.assertTrue(result.outputs["changed"])

    def test_gh_project_issue_estimate_set_reports_field_update_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.field_number.set", with_={"repository": "owner/repo", "issue_number": 7, "project_id": "PVT_demo", "field": "Estimate", "value": 5})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.field_number.set")
        resolved = ResolvedOperation("gh.project.issue.field_number.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "field_update_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_field_number_set.command_failed")

    def test_git_branch_probe_returns_branch_value_for_expression_surface(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=())
        operation = get_public_connector_registry().get_operation("git.branch")
        resolved = ResolvedExpressionProbe(
            reference="git.branch",
            connector_namespace="git",
            operation=operation,  # type: ignore[arg-type]
            source="public",
            expression_text="git.branch.value",
            fields=("value",),
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="refs/heads/feature/demo\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["value"], "feature/demo")
        self.assertEqual(result.outputs["ref"], "refs/heads/feature/demo")
        self.assertFalse(result.outputs["detached"])
        self.assertEqual(result.outputs["repository_root"], "/tmp/demo-repo")

    def test_git_branch_probe_returns_detached_head_state(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branch")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branch")
        resolved = ResolvedOperation("git.branch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="detached\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.outputs["value"])
        self.assertIsNone(result.outputs["ref"])
        self.assertTrue(result.outputs["detached"])

    def test_git_branch_probe_fails_on_unexpected_symbolic_ref_shape(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branch")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branch")
        resolved = ResolvedOperation("git.branch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="HEAD\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_branch.invalid_ref")

    def test_git_repo_probe_returns_canonical_repository_context(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.repo")),), steps=())
        operation = get_public_connector_registry().get_operation("git.repo")
        resolved = ResolvedOperation("git.repo", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
                self._completed(returncode=0, stdout="origin/main\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            result.outputs,
            {
                "exists": True,
                "root": "/tmp/demo-repo",
                "git_dir": "/tmp/demo-repo/.git",
                "inside_work_tree": True,
                "bare": False,
                "head_ref": "feature/demo",
                "worktree_path": "/tmp/demo-repo",
                "common_dir": "/tmp/demo-repo/.git",
                "default_branch": "main",
            },
        )

    def test_git_repo_probe_fails_on_unexpected_remote_head_format(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.repo")),), steps=())
        operation = get_public_connector_registry().get_operation("git.repo")
        resolved = ResolvedOperation("git.repo", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=0, stdout="true\n", stderr=""),
                self._completed(returncode=0, stdout="false\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo/.git\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="detached\n"),
                self._completed(returncode=0, stdout="main\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_repo.invalid_remote_head")

    def test_git_repo_probe_surfaces_external_failure_details(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.repo")),), steps=())
        operation = get_public_connector_registry().get_operation("git.repo")
        resolved = ResolvedOperation("git.repo", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.git_repo.command_failed")
        self.assertEqual(result.diagnostics[0].details["classification"], "permission_denied")
        self.assertEqual(result.diagnostics[0].details["external_tool"], "git")

    def test_git_probe_surfaces_bootstrap_failure_before_operation_logic(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branch")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branch")
        resolved = ResolvedOperation("git.branch", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=128, stdout="", stderr="fatal: not a git repository"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "not_repository")
        self.assertEqual(result.diagnostics[0].code, "operation.command_failed")
        self.assertEqual(run.call_count, 1)

    def test_gh_issue_probe_resolves_named_argument_from_workflow_inputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"repository": "owner/repo", "issue_number": 1}, guards=(), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedExpressionProbe(
            reference="gh.issue",
            connector_namespace="gh",
            operation=operation,  # type: ignore[arg-type]
            source="public",
            expression_text="gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state",
            fields=("state",),
            arguments=(("repository", ReferenceNode(start=0, end=17, parts=("inputs", "repository"))), ("issue_number", ReferenceNode(start=0, end=19, parts=("inputs", "issue_number")))),
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"nameWithOwner":"owner/repo","issue":{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":{"nodes":[]},"assignees":{"nodes":[]},"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"stateReason":null,"projectItems":{"nodes":[]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["state"], "OPEN")
        self.assertEqual(result.outputs["repository"]["nameWithOwner"], "owner/repo")

    def test_gh_issue_probe_allows_explicit_repository_override_over_context(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            connector_contexts={"gh": {"repository": "fork/repo"}},
            guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 1})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"data":{"repository":{"nameWithOwner":"owner/repo","issue":{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":{"nodes":[]},"assignees":{"nodes":[]},"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"stateReason":null,"projectItems":{"nodes":[]}}}}}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["repository"]["nameWithOwner"], "owner/repo")
        self.assertFalse(any(diagnostic.code.endswith("repository_conflict") for diagnostic in result.diagnostics))

    def test_gh_issue_probe_maps_not_found_to_local_failure_mode(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 999})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="GraphQL: Could not resolve to an issue with the number of 999.\n"),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_issue.not_found")

    def test_gh_issue_probe_reports_invalid_json(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue", with_={"repository": "owner/repo", "issue_number": 1})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number": 1', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_issue.invalid_json")

    def test_gh_project_issue_probe_returns_project_local_fields(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.issue", with_={"repository": "owner/repo", "issue_number": 1, "project_id": "PVT_demo"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue")
        resolved = ResolvedOperation("gh.project.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout=(
                        '{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_1","project":{"id":"PVT_demo","title":"Checklists"},'
                        '"fieldValues":{"nodes":[{"name":"In progress","field":{"name":"Status"}},{"name":"Task","field":{"name":"Type"}},'
                        '{"name":"P1","field":{"name":"Priority"}},{"title":"Sprint 12","field":{"name":"Iteration"}},{"name":"M","field":{"name":"Size"}},'
                        '{"number":5,"field":{"name":"Estimate"}}]}}]}}}}}'
                    ),
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["exists"])
        self.assertEqual(result.outputs["status"], "In progress")
        self.assertEqual(result.outputs["type"], "Task")
        self.assertEqual(result.outputs["iteration"], "Sprint 12")
        self.assertEqual(result.outputs["estimate"], 5)
        self.assertEqual(result.outputs["item_id"], "PVTI_1")

    def test_gh_project_issue_probe_reports_issue_not_in_project_via_exists_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.issue", with_={"repository": "owner/repo", "issue_number": 1, "project_id": "PVT_demo"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue")
        resolved = ResolvedOperation("gh.project.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists"}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["exists"])
        self.assertIsNone(result.outputs["status"])

    def test_gh_project_issue_probe_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.issue", with_={"repository": "owner/repo", "issue_number": 1, "project_id": "PVT_missing"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue")
        resolved = ResolvedOperation("gh.project.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_issue.project_not_found")

    def test_gh_project_probe_returns_identity_facts(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project", with_={"project_id": "PVT_demo"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project")
        resolved = ResolvedOperation("gh.project", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists"}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["exists"])
        self.assertEqual(result.outputs["id"], "PVT_demo")
        self.assertEqual(result.outputs["title"], "Checklists")

    def test_gh_project_probe_reports_project_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project", with_={"project_id": "PVT_missing"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project")
        resolved = ResolvedOperation("gh.project", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project.project_not_found")

    def test_gh_project_probe_reports_invalid_json(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project", with_={"project_id": "PVT_demo"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project")
        resolved = ResolvedOperation("gh.project", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project.invalid_json")

    def test_gh_project_field_probe_returns_single_select_field_facts(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field", with_={"project_id": "PVT_demo", "field": "Priority"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field")
        resolved = ResolvedOperation("gh.project.field", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F1","name":"Priority","dataType":"SINGLE_SELECT","options":[{"id":"O1","name":"P0"},{"id":"O2","name":"P1"}]},{"__typename":"ProjectV2Field","id":"F2","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["exists"])
        self.assertEqual(result.outputs["name"], "Priority")
        self.assertEqual(result.outputs["kind"], "single_select")
        self.assertEqual(result.outputs["options"], ["P0", "P1"])

    def test_gh_project_field_probe_returns_number_field_facts(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field", with_={"project_id": "PVT_demo", "field": "Estimate"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field")
        resolved = ResolvedOperation("gh.project.field", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"__typename":"ProjectV2Field","id":"F2","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["exists"])
        self.assertEqual(result.outputs["kind"], "number")
        self.assertEqual(result.outputs["options"], [])

    def test_gh_project_field_probe_reports_missing_field_via_exists_false(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field", with_={"project_id": "PVT_demo", "field": "Priority"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field")
        resolved = ResolvedOperation("gh.project.field", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["exists"])
        self.assertEqual(result.outputs["options"], [])

    def test_gh_project_field_probe_reports_project_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field", with_={"project_id": "PVT_missing", "field": "Priority"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field")
        resolved = ResolvedOperation("gh.project.field", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_field.project_not_found")

    def test_gh_project_field_option_probe_reports_existing_option(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field.option", with_={"project_id": "PVT_demo", "field": "Priority", "option": "P1"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field.option")
        resolved = ResolvedOperation("gh.project.field.option", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F1","name":"Priority","dataType":"SINGLE_SELECT","options":[{"id":"O1","name":"P0"},{"id":"O2","name":"P1"}]},{"__typename":"ProjectV2IterationField","id":"F3","name":"Iteration","configuration":{"iterations":[{"title":"Sprint 12"}]}}]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["exists"])

    def test_gh_project_field_option_probe_reports_missing_option(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field.option", with_={"project_id": "PVT_demo", "field": "Priority", "option": "P9"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field.option")
        resolved = ResolvedOperation("gh.project.field.option", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"__typename":"ProjectV2SingleSelectField","id":"F1","name":"Priority","dataType":"SINGLE_SELECT","options":[{"id":"O1","name":"P0"},{"id":"O2","name":"P1"}]},{"__typename":"ProjectV2IterationField","id":"F3","name":"Iteration","configuration":{"iterations":[{"title":"Sprint 12"}]}}]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["exists"])

    def test_gh_project_field_option_probe_reports_missing_field_via_exists_false(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field.option", with_={"project_id": "PVT_demo", "field": "Priority", "option": "P1"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field.option")
        resolved = ResolvedOperation("gh.project.field.option", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[]}}}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.outputs["exists"])

    def test_gh_project_field_option_probe_reports_project_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.project.field.option", with_={"project_id": "PVT_missing", "field": "Priority", "option": "P1"})),), steps=())
        operation = get_public_connector_registry().get_operation("gh.project.field.option")
        resolved = ResolvedOperation("gh.project.field.option", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_project_field_option.project_not_found")

    def _completed(self, *, returncode: int, stdout: str, stderr: str):
        class Completed:
            pass

        completed = Completed()
        completed.returncode = returncode
        completed.stdout = stdout
        completed.stderr = stderr
        return completed


if __name__ == "__main__":
    unittest.main()
