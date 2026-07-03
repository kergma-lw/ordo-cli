import importlib
import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe, execute_action
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import check_workflow
from ordo.runtime.guard_expressions import LiteralNode, ReferenceNode
from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation
from ordo.connectors.registry import get_public_connector_registry
from tests.support import STANDARD_CONNECTOR_PROVIDER


class OperationTest(unittest.TestCase):
    def test_migrated_git_probe_modules_publish_through_info_hook(self) -> None:
        git_repo_module = importlib.import_module("connectors.git.probes.repo")
        git_branch_module = importlib.import_module("connectors.git.probes.branch")
        git_worktree_module = importlib.import_module("connectors.git.probes.worktree")
        git_worktrees_module = importlib.import_module("connectors.git.probes.worktrees")
        git_branches_module = importlib.import_module("connectors.git.probes.branches")
        git_stash_module = importlib.import_module("connectors.git.probes.stash")
        git_state_module = importlib.import_module("connectors.git.probes.state")
        git_ref_module = importlib.import_module("connectors.git.probes.ref")
        git_upstream_module = importlib.import_module("connectors.git.probes.upstream")
        git_range_module = importlib.import_module("connectors.git.probes.range")
        repo_info = git_repo_module.info()
        branch_info = git_branch_module.info()
        worktree_info = git_worktree_module.info()
        worktrees_info = git_worktrees_module.info()
        branches_info = git_branches_module.info()
        stash_info = git_stash_module.info()
        state_info = git_state_module.info()
        ref_info = git_ref_module.info()
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
        self.assertEqual(state_info.name, "state")
        self.assertEqual(state_info.kind, "probe")
        self.assertIs(state_info.handler, git_state_module.run)
        self.assertEqual(ref_info.name, "ref")
        self.assertEqual(ref_info.kind, "probe")
        self.assertIs(ref_info.handler, git_ref_module.run)
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
        gh_close = registry.get_operation("gh.issue.close")
        shell_command = registry.get_operation("shell.command")

        self.assertEqual(gh_issue.failure_modes, ("issue_not_found", "probe_failed"))
        self.assertEqual(gh_close.failure_modes, ("issue_not_found", "close_blocked"))
        self.assertEqual(shell_command.failure_modes, ("command_failed", "action_failed"))

    def test_git_worktree_returns_structured_probe_observations(self) -> None:
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
        self.assertFalse(result.observations["clean"])
        self.assertEqual(result.observations["dirty_paths"], ["README.md", "tmp.txt"])
        self.assertTrue(result.observations["has_untracked"])
        self.assertFalse(result.observations["has_staged_changes"])
        self.assertTrue(result.observations["has_unstaged_changes"])
        self.assertEqual(result.observations["repository_root"], "/tmp/demo-repo")

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
        self.assertFalse(result.observations["clean"])
        self.assertEqual(result.observations["dirty_paths"], ["staged.txt", "unstaged.txt", "tmp.txt"])
        self.assertTrue(result.observations["has_untracked"])
        self.assertTrue(result.observations["has_staged_changes"])
        self.assertTrue(result.observations["has_unstaged_changes"])

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
        self.assertEqual(result.observations["count"], 2)
        self.assertEqual(result.observations["current_path"], "/tmp/demo-repo")
        self.assertEqual(
            result.observations["items"],
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
        self.assertEqual(result.observations["count"], 3)
        self.assertEqual(result.observations["current"], "feature/demo")
        self.assertEqual(
            result.observations["items"],
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
        self.assertIsNone(result.observations["current"])

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
        self.assertEqual(result.observations["count"], 2)
        self.assertEqual(
            result.observations["items"],
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
            result.observations,
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
            result.observations,
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
        self.assertEqual(result.observations["name"], "refs/heads/missing")
        self.assertFalse(result.observations["exists"])
        self.assertIsNone(result.observations["oid"])
        self.assertFalse(result.observations["symbolic"])
        self.assertIsNone(result.observations["symbolic_target"])

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
            result.observations,
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
        self.assertFalse(result.observations["configured"])
        self.assertIsNone(result.observations["branch"])
        self.assertIsNone(result.observations["upstream_ref"])

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
        self.assertFalse(result.observations["configured"])
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertIsNone(result.observations["upstream_ref"])

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
            result.observations,
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
        self.assertIsNone(result.observations["merge_base_oid"])
        self.assertEqual(result.observations["ahead_count"], 7)
        self.assertEqual(result.observations["behind_count"], 0)

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
                return OperationResult(status="ok", observations={"value": "main"})
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
        self.assertEqual(result.observations["exit_code"], 0)

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertTrue(result.observations["changed"])

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertFalse(result.observations["changed"])

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertEqual(result.observations["commit"], "abc1234567890")

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertEqual(result.observations["previous_commit"], "abc111")
        self.assertEqual(result.observations["commit"], "def5678901234")

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
        self.assertEqual(result.observations["previous_commit"], "abc111")
        self.assertEqual(result.observations["commit"], "def5678901234")

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
        self.assertEqual(result.observations["reverted_commit"], "abc123")
        self.assertEqual(result.observations["revert_commit"], "def5678901234")
        self.assertEqual(result.observations["branch"], "feature/demo")

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
        self.assertEqual(result.observations["merged_ref"], "mainsha")
        self.assertEqual(result.observations["head_commit"], "mergedhead")
        self.assertEqual(result.observations["branch"], "feature/demo")

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
        self.assertEqual(result.observations["merged_ref"], "mainsha")
        self.assertEqual(result.observations["head_commit"], "mergedhead")
        self.assertEqual(result.observations["branch"], "feature/demo")

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertEqual(result.observations["onto"], "mainsha")
        self.assertEqual(result.observations["head_commit"], "rebasedhead")

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
        self.assertEqual(result.observations["picked_commit"], "abc123")
        self.assertEqual(result.observations["head_commit"], "def5678901234")
        self.assertEqual(result.observations["branch"], "main")

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
        self.assertEqual(result.observations["remote"], "origin")
        self.assertTrue(result.observations["fetched"])

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
        self.assertEqual(result.observations["remote"], "origin")
        self.assertEqual(result.observations["branch"], "feature/demo")

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
        self.assertEqual(result.observations["remote"], "origin")
        self.assertEqual(result.observations["branch"], "feature/demo")

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertEqual(result.observations["start_point"], "abc1234567890")

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
        self.assertEqual(result.observations["branch"], "feature/demo")
        self.assertEqual(result.observations["start_point"], "feedface12345678")

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
        self.assertEqual(result.observations["branch"], "feature/demo")

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
            guards=(Guard(OperationRef("gh.issue", with_={"issue": "owner/repo#1"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedOperation("gh.issue", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":[],"assignees":[],"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"repository":{"nameWithOwner":"owner/repo"},"stateReason":null,"projectItems":[]}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["number"], 1)

    def test_gh_probe_surfaces_bootstrap_failure_before_operation_logic(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue", with_={"issue": "owner/repo#1"})),),
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

    def test_unimplemented_operation_returns_structured_failure(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="move", operation=OperationRef("gh.project_set_status")),))
        operation = get_public_connector_registry().get_operation("gh.project_set_status")
        resolved = ResolvedOperation("gh.project_set_status", "gh", operation, "public")  # type: ignore[arg-type]

        result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "action_not_implemented")
        self.assertEqual(result.diagnostics[0].code, "operation.not_implemented")

    def test_gh_issue_close_closes_open_issue(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"issue_ref": "owner/repo#7"})),))
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
        self.assertEqual(result.observations["issue_ref"], "owner/repo#7")
        self.assertEqual(result.observations["state"], "CLOSED")
        self.assertTrue(result.observations["closed"])
        self.assertEqual(run.call_count, 3)

    def test_gh_issue_close_is_noop_for_closed_issue(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"issue_ref": "owner/repo#7"})),))
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
        self.assertTrue(result.observations["closed"])
        self.assertEqual(run.call_count, 2)

    def test_gh_issue_close_reports_issue_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"issue_ref": "owner/repo#7"})),))
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
        workflow = Workflow(version=0, workflow="demo", guards=(), steps=(Step(name="close", operation=OperationRef("gh.issue.close", with_={"issue_ref": "owner/repo#7"})),))
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
                self._completed(returncode=0, stdout='{"number":17,"url":"https://github.com/owner/repo/issues/17","title":"Add checklist"}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["issue_ref"], "owner/repo#17")
        self.assertEqual(result.observations["repository"], "owner/repo")
        self.assertEqual(result.observations["number"], 17)
        self.assertEqual(result.observations["title"], "Add checklist")

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

    def test_gh_issue_comment_add_creates_comment(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"issue_ref": "owner/repo#17", "body": "Looks good."})),),
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
        self.assertEqual(result.observations["issue_ref"], "owner/repo#17")
        self.assertEqual(result.observations["comment_id"], "IC_1")
        self.assertEqual(result.observations["body"], "Looks good.")

    def test_gh_issue_comment_add_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"issue_ref": "owner/repo#999", "body": "Looks good."})),),
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
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"issue_ref": "owner/repo#17", "body": "   "})),),
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
            steps=(Step(name="comment", operation=OperationRef("gh.issue.comment.add", with_={"issue_ref": "owner/repo#17", "body": "Looks good."})),),
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

    def test_gh_issue_body_replace_updates_body(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"issue_ref": "owner/repo#17", "body": "Updated body."})),),
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
        self.assertEqual(result.observations["issue_ref"], "owner/repo#17")
        self.assertEqual(result.observations["body"], "Updated body.")
        self.assertTrue(result.observations["changed"])

    def test_gh_issue_body_replace_is_noop_for_same_body(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"issue_ref": "owner/repo#17", "body": "Same body."})),),
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
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub issue body is already set")

    def test_gh_issue_body_replace_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"issue_ref": "owner/repo#999", "body": "Updated body."})),),
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
            steps=(Step(name="replace-body", operation=OperationRef("gh.issue.body.replace", with_={"issue_ref": "owner/repo#17", "body": "Updated body."})),),
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
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"issue_ref": "owner/repo#17", "text": "New section."})),),
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
        self.assertEqual(result.observations["body"], "Old body.\n\nNew section.")
        self.assertTrue(result.observations["changed"])

    def test_gh_issue_body_append_uses_custom_separator(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"issue_ref": "owner/repo#17", "text": "tail", "separator": ""})),),
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
        self.assertEqual(result.observations["body"], "headtail")

    def test_gh_issue_body_append_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"issue_ref": "owner/repo#999", "text": "New section."})),),
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
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"issue_ref": "owner/repo#17", "text": "   "})),),
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
            steps=(Step(name="append-body", operation=OperationRef("gh.issue.body.append", with_={"issue_ref": "owner/repo#17", "text": "New section."})),),
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
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo"})),),
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
        self.assertEqual(result.observations["issue_ref"], "owner/repo#7")
        self.assertEqual(result.observations["project_id"], "PVT_demo")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertTrue(result.observations["added"])

    def test_gh_project_issue_add_is_noop_for_existing_project_item(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo"})),),
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
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertFalse(result.observations["added"])

    def test_gh_project_issue_add_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing"})),),
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
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo"})),),
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
            steps=(Step(name="add", operation=OperationRef("gh.project.issue.add", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo"})),),
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

    def test_gh_project_issue_status_set_updates_project_status(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "status": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"},{"id":"OPT_2","name":"In progress"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["status"], "In progress")
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_status_set_is_noop_for_same_status(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "status": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"In progress","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue status is already set")

    def test_gh_project_issue_status_set_reports_status_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "status": "Done"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "status_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_status_set.status_not_found")

    def test_gh_project_issue_status_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "status": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_status_set.project_not_found")

    def test_gh_project_issue_status_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "status": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_status_set.issue_not_found")

    def test_gh_project_issue_status_set_reports_status_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-status", operation=OperationRef("gh.project.issue.status.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "status": "In progress"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.status.set")
        resolved = ResolvedOperation("gh.project.issue.status.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Backlog","field":{"name":"Status"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_1","name":"Status","options":[{"id":"OPT_1","name":"Backlog"},{"id":"OPT_2","name":"In progress"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "status_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_status_set.command_failed")

    def test_gh_project_issue_iteration_set_updates_project_iteration(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14},{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["iteration"], "Sprint 12")
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_iteration_set_is_noop_for_same_iteration(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 12","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue iteration is already set")

    def test_gh_project_issue_iteration_set_reports_iteration_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "iteration": "Sprint 13"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14}]}}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "iteration_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_iteration_set.iteration_not_found")

    def test_gh_project_issue_iteration_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_iteration_set.project_not_found")

    def test_gh_project_issue_iteration_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_iteration_set.issue_not_found")

    def test_gh_project_issue_iteration_set_reports_iteration_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-iteration", operation=OperationRef("gh.project.issue.iteration.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "iteration": "Sprint 12"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.iteration.set")
        resolved = ResolvedOperation("gh.project.issue.iteration.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"title":"Sprint 11","field":{"name":"Iteration"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTIF_1","name":"Iteration","configuration":{"iterations":[{"id":"IT_11","title":"Sprint 11","startDate":"2026-07-01","duration":14},{"id":"IT_12","title":"Sprint 12","startDate":"2026-07-15","duration":14}]}}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "iteration_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_iteration_set.command_failed")

    def test_gh_project_issue_priority_set_updates_priority(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "priority": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["priority"], "P1")
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_priority_set_is_noop_for_same_priority(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "priority": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P1","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue priority is already set")

    def test_gh_project_issue_priority_set_reports_priority_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "priority": "P0"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "priority_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_priority_set.priority_not_found")

    def test_gh_project_issue_priority_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "priority": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_priority_set.project_not_found")

    def test_gh_project_issue_priority_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "priority": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_priority_set.issue_not_found")

    def test_gh_project_issue_priority_set_reports_priority_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-priority", operation=OperationRef("gh.project.issue.priority.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "priority": "P1"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.priority.set")
        resolved = ResolvedOperation("gh.project.issue.priority.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"P2","field":{"name":"Priority"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_P","name":"Priority","options":[{"id":"OPT_P1","name":"P1"},{"id":"OPT_P2","name":"P2"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "priority_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_priority_set.command_failed")

    def test_gh_project_issue_type_set_updates_type(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "type": "Bug"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["type"], "Bug")
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_type_set_is_noop_for_same_type(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "type": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue type is already set")

    def test_gh_project_issue_type_set_reports_type_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "type": "Story"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "type_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_type_set.type_not_found")

    def test_gh_project_issue_type_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "type": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_type_set.project_not_found")

    def test_gh_project_issue_type_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "type": "Task"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_type_set.issue_not_found")

    def test_gh_project_issue_type_set_reports_type_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-type", operation=OperationRef("gh.project.issue.type.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "type": "Bug"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.type.set")
        resolved = ResolvedOperation("gh.project.issue.type.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"Task","field":{"name":"Type"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_T","name":"Type","options":[{"id":"OPT_TASK","name":"Task"},{"id":"OPT_BUG","name":"Bug"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "type_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_type_set.command_failed")

    def test_gh_project_issue_size_set_updates_size(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "size": "L"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["size"], "L")
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_size_set_is_noop_for_same_size(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "size": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue size is already set")

    def test_gh_project_issue_size_set_reports_size_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "size": "XL"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "size_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_size_set.size_not_found")

    def test_gh_project_issue_size_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "size": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_size_set.project_not_found")

    def test_gh_project_issue_size_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "size": "M"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_size_set.issue_not_found")

    def test_gh_project_issue_size_set_reports_size_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-size", operation=OperationRef("gh.project.issue.size.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "size": "L"})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.size.set")
        resolved = ResolvedOperation("gh.project.issue.size.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"name":"M","field":{"name":"Size"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTSSF_S","name":"Size","options":[{"id":"OPT_M","name":"M"},{"id":"OPT_L","name":"L"}]}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "size_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_size_set.command_failed")

    def test_gh_project_issue_estimate_set_updates_estimate(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "estimate": 5})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"PVTI_7"}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["item_id"], "PVTI_7")
        self.assertEqual(result.observations["estimate"], 5)
        self.assertTrue(result.observations["changed"])

    def test_gh_project_issue_estimate_set_is_noop_for_same_estimate(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "estimate": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["changed"])
        self.assertEqual(result.summary, "GitHub project issue estimate is already set")

    def test_gh_project_issue_estimate_set_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_missing", "estimate": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":null}}', stderr=""),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "project_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_estimate_set.project_not_found")

    def test_gh_project_issue_estimate_set_reports_issue_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#999", "project_id": "PVT_demo", "estimate": 3})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=1, stdout="", stderr="issue not found"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "issue_not_found")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_estimate_set.issue_not_found")

    def test_gh_project_issue_estimate_set_reports_estimate_invalid_for_bad_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "estimate": True})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [self._completed(returncode=0, stdout="authenticated\n", stderr="")]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "estimate_invalid")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_estimate_set.estimate_invalid")

    def test_gh_project_issue_estimate_set_reports_estimate_blocked(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(),
            steps=(Step(name="set-estimate", operation=OperationRef("gh.project.issue.estimate.set", with_={"issue_ref": "owner/repo#7", "project_id": "PVT_demo", "estimate": 5})),),
        )
        operation = get_public_connector_registry().get_operation("gh.project.issue.estimate.set")
        resolved = ResolvedOperation("gh.project.issue.estimate.set", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"data":{"repository":{"issue":{"projectItems":{"nodes":[{"id":"PVTI_7","project":{"id":"PVT_demo"},"fieldValues":{"nodes":[{"number":3,"field":{"name":"Estimate"}}]}}]}}}}}', stderr=""),
                self._completed(returncode=0, stdout='{"data":{"node":{"id":"PVT_demo","title":"Checklists","fields":{"nodes":[{"id":"PVTNF_E","name":"Estimate","dataType":"NUMBER"}]}}}}', stderr=""),
                self._completed(returncode=1, stdout="", stderr="permission denied"),
            ]

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "estimate_blocked")
        self.assertEqual(result.diagnostics[0].code, "action.gh_project_issue_estimate_set.command_failed")

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
        self.assertEqual(result.observations["value"], "feature/demo")
        self.assertEqual(result.observations["ref"], "refs/heads/feature/demo")
        self.assertFalse(result.observations["detached"])
        self.assertEqual(result.observations["repository_root"], "/tmp/demo-repo")

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
        self.assertIsNone(result.observations["value"])
        self.assertIsNone(result.observations["ref"])
        self.assertTrue(result.observations["detached"])

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
            result.observations,
            {
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
        workflow = Workflow(version=0, workflow="demo", inputs={"issue": "owner/repo#1"}, guards=(), steps=())
        operation = get_public_connector_registry().get_operation("gh.issue")
        resolved = ResolvedExpressionProbe(
            reference="gh.issue",
            connector_namespace="gh",
            operation=operation,  # type: ignore[arg-type]
            source="public",
            expression_text="gh.issue(issue=inputs.issue).state",
            fields=("state",),
            arguments=(("issue", ReferenceNode(start=0, end=12, parts=("inputs", "issue"))),),
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(
                    returncode=0,
                    stdout='{"id":"I_1","number":1,"title":"Demo","state":"OPEN","closed":false,"url":"https://example.test","body":"x","author":{"login":"octo"},"labels":[],"assignees":[],"milestone":null,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-02T00:00:00Z","closedAt":null,"comments":{"totalCount":0},"reactionGroups":[],"repository":{"nameWithOwner":"owner/repo"},"stateReason":null,"projectItems":[]}',
                    stderr="",
                ),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["state"], "OPEN")
        self.assertEqual(result.observations["repository"]["nameWithOwner"], "owner/repo")

    def test_gh_issue_probe_maps_not_found_to_local_failure_mode(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue", with_={"issue": "owner/repo#999"})),), steps=())
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
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("gh.issue", with_={"issue": "owner/repo#1"})),), steps=())
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
            guards=(Guard(OperationRef("gh.project.issue", with_={"issue": "owner/repo#1", "project": "PVT_demo"})),),
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
        self.assertTrue(result.observations["exists"])
        self.assertEqual(result.observations["status"], "In progress")
        self.assertEqual(result.observations["type"], "Task")
        self.assertEqual(result.observations["iteration"], "Sprint 12")
        self.assertEqual(result.observations["estimate"], 5)

    def test_gh_project_issue_probe_reports_issue_not_in_project_via_exists_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.issue", with_={"issue": "owner/repo#1", "project": "PVT_demo"})),),
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
        self.assertFalse(result.observations["exists"])
        self.assertIsNone(result.observations["status"])

    def test_gh_project_issue_probe_reports_project_not_found(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.project.issue", with_={"issue": "owner/repo#1", "project": "PVT_missing"})),),
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
