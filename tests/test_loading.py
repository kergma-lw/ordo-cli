import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.profile import Profile
from ordo.model.workflow import Workflow
from ordo.runtime import LoadError, load_profile_file, load_profile_text, load_workflow_text, load_yaml_document


class LoadingTest(unittest.TestCase):
    def test_loads_workflow_yaml_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  issue: repo#1
                guards:
                  - uses: git.worktree
                steps:
                  - name: inspect
                    uses: gh.issue
                    register: issue
                    with:
                      issue: repo#1
                """
            )
        )

        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(workflow.to_contract()["steps"][0]["uses"], "gh.issue")
        self.assertEqual(workflow.to_contract()["steps"][0]["register"], "issue")

    def test_loads_expr_guard_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                guards:
                  - git.worktree.clean and git.branch != "main"
                steps: []
                """
            )
        )

        self.assertEqual(workflow.guards[0].expr, 'git.worktree.clean and git.branch != "main"')
        self.assertEqual(workflow.to_contract()["guards"][0], 'git.worktree.clean and git.branch != "main"')

    def test_loads_profile_yaml_into_typed_model(self) -> None:
        profile = load_profile_text(
            textwrap.dedent(
                """
                name: backend-default
                inputs:
                  test_command: .venv/bin/python -m pytest
                checks:
                  - unit
                overrides:
                  - target: shell.command
                    with:
                      command: .venv/bin/python -m pytest
                    reason: repo default verify command
                """
            )
        )

        self.assertIsInstance(profile, Profile)
        self.assertEqual(profile.to_contract()["overrides"][0]["target"], "shell.command")

    def test_loader_normalizes_yaml_merge_without_distinct_runtime_semantics(self) -> None:
        merged = load_yaml_document(
            textwrap.dedent(
                """
                defaults: &defaults
                  issue: repo#1
                  branch: keep

                inputs:
                  <<: *defaults
                  iteration: current
                """
            )
        )

        plain = {
            "defaults": {"issue": "repo#1", "branch": "keep"},
            "inputs": {"issue": "repo#1", "branch": "keep", "iteration": "current"},
        }

        self.assertEqual(merged, plain)

    def test_loader_returns_structured_error_for_invalid_yaml(self) -> None:
        with self.assertRaises(LoadError) as context:
            load_workflow_text("version: [1\nworkflow: broken\n")

        diagnostic = context.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "load.yaml.syntax")
        self.assertEqual(diagnostic.level, "error")

    def test_loader_rejects_non_json_shaped_values(self) -> None:
        with self.assertRaises(LoadError) as context:
            load_yaml_document("created_at: 2026-06-26\n")

        self.assertEqual(context.exception.diagnostics[0].code, "load.json_value.type")

    def test_loader_can_read_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "profile.yaml"
            path.write_text("name: demo\nchecks: []\noverrides: []\n", encoding="utf-8")

            profile = load_profile_file(path)

        self.assertEqual(profile.name, "demo")


if __name__ == "__main__":
    unittest.main()
