import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe, execute_action
from ordo.model.runtime import OperationResult
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime.guard_expressions import LiteralNode, ReferenceNode
from ordo.runtime.resolution import ResolvedExpressionProbe, ResolvedOperation
from ordo.connectors.registry import get_public_connector_registry


class OperationTest(unittest.TestCase):
    def test_git_clean_worktree_returns_structured_probe_observations(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.clean_worktree")),), steps=())
        operation = get_public_connector_registry().get_operation("git.clean_worktree")
        resolved = ResolvedOperation("git.clean_worktree", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = " M README.md\n?? tmp.txt\n"
            run.return_value.stderr = ""

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.observations["clean"])
        self.assertEqual(result.observations["dirty_paths"], ["README.md", "tmp.txt"])

    def test_git_branch_not_main_blocks_main_branch(self) -> None:
        workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("git.branch_not_main")),), steps=())
        operation = get_public_connector_registry().get_operation("git.branch_not_main")
        resolved = ResolvedOperation("git.branch_not_main", "git", operation, "public")  # type: ignore[arg-type]

        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "main\n"
            run.return_value.stderr = ""

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
            run.return_value.returncode = 0
            run.return_value.stdout = "hi\n"
            run.return_value.stderr = ""

            result = execute_action(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.raw["stdout"], "hi\n")
        self.assertEqual(result.observations["returncode"], 0)

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
            run.return_value.returncode = 0
            run.return_value.stdout = '{"number":1,"title":"Demo","state":"OPEN","body":"x","url":"https://example.test"}'
            run.return_value.stderr = ""

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["issue"]["number"], 1)

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
            run.return_value.returncode = 0
            run.return_value.stdout = "feature/demo\n"
            run.return_value.stderr = ""

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["value"], "feature/demo")

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
            run.return_value.returncode = 0
            run.return_value.stdout = '{"number":1,"title":"Demo","state":"OPEN","body":"x","url":"https://example.test"}'
            run.return_value.stderr = ""

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.observations["status"], "OPEN")


if __name__ == "__main__":
    unittest.main()
