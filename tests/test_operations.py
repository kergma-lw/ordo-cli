import importlib
import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe, execute_action
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime.guard_expressions import LiteralNode, ReferenceNode
from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation
from ordo.connectors.registry import get_public_connector_registry


class OperationTest(unittest.TestCase):
    def test_migrated_git_probe_modules_publish_through_info_hook(self) -> None:
        git_branch_module = importlib.import_module("connectors.git.probes.branch")
        git_worktree_module = importlib.import_module("connectors.git.probes.worktree")
        branch_info = git_branch_module.info()
        worktree_info = git_worktree_module.info()

        self.assertEqual(branch_info.name, "branch")
        self.assertEqual(branch_info.kind, "probe")
        self.assertIs(branch_info.handler, git_branch_module.run)
        self.assertEqual(worktree_info.name, "worktree")
        self.assertEqual(worktree_info.kind, "probe")
        self.assertIs(worktree_info.handler, git_worktree_module.run)

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

    def test_git_clean_worktree_returns_structured_probe_observations(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.clean_worktree")),), steps=())
        operation = get_public_connector_registry().get_operation("git.clean_worktree")
        resolved = ResolvedOperation("git.clean_worktree", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout=" M README.md\n?? tmp.txt\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["clean"])
        self.assertEqual(result.observations["dirty_paths"], ["README.md", "tmp.txt"])
        self.assertEqual(result.observations["repository_root"], "/tmp/demo-repo")

    def test_git_branch_not_main_blocks_main_branch(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branch_not_main")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branch_not_main")
        resolved = ResolvedOperation("git.branch_not_main", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.side_effect = [
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="/tmp/demo-repo\n", stderr=""),
                self._completed(returncode=0, stdout="main\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "guard_failed")
        self.assertEqual(result.observations["current_branch"], "main")
        self.assertEqual(result.diagnostics[0].code, "guard.branch_main")

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
                self._completed(returncode=0, stdout="feature/demo\n", stderr=""),
            ]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["value"], "feature/demo")
        self.assertEqual(result.observations["repository_root"], "/tmp/demo-repo")

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
