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
        merge = registry.get_operation("git.merge_to_main_ff")

        self.assertEqual(branch.failure_modes, ("probe_failed",))
        self.assertEqual(worktree.failure_modes, ("probe_failed",))
        self.assertEqual(merge.failure_modes, ("non_fast_forward", "action_failed"))

    def test_gh_and_shell_operation_contracts_no_longer_primary_own_shared_bootstrap_failures(self) -> None:
        registry = get_public_connector_registry()

        gh_issue = registry.get_operation("gh.issue")
        gh_close = registry.get_operation("gh.close_issue")
        shell_command = registry.get_operation("shell.command")

        self.assertEqual(gh_issue.failure_modes, ("issue_not_found", "probe_failed"))
        self.assertEqual(gh_close.failure_modes, ("issue_not_found", "action_failed"))
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

    def test_gh_issue_view_returns_structured_probe_data(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue.view", with_={"issue": "owner/repo#1"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.view")
        resolved = ResolvedOperation("gh.issue.view", "gh", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":1,"title":"Demo","state":"OPEN","body":"x","url":"https://example.test"}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["issue"]["number"], 1)

    def test_gh_probe_surfaces_bootstrap_failure_before_operation_logic(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            guards=(Guard(OperationRef("gh.issue.view", with_={"issue": "owner/repo#1"})),),
            steps=(),
        )
        operation = get_public_connector_registry().get_operation("gh.issue.view")
        resolved = ResolvedOperation("gh.issue.view", "gh", operation, "public")  # type: ignore[arg-type]

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
            expression_text="gh.issue(issue=inputs.issue).status",
            fields=("status",),
            arguments=(("issue", ReferenceNode(start=0, end=12, parts=("inputs", "issue"))),),
        )

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="authenticated\n", stderr=""),
                self._completed(returncode=0, stdout='{"number":1,"title":"Demo","state":"OPEN","body":"x","url":"https://example.test"}', stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["status"], "OPEN")

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
