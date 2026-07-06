import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.profile import Profile
from ordo.model.workflow import Workflow
from ordo.runtime import LoadError, load_profile_file, load_profile_text, load_workflow_file, load_workflow_text, load_yaml_document


class LoadingTest(unittest.TestCase):
    def test_loads_workflow_yaml_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  issue: repo#1
                blocks:
                  - guards:
                      - uses: git.worktree
                  - steps:
                      - name: inspect
                        uses: gh.issue
                        register: issue
                        with:
                          issue: repo#1
                """
            )
        )

        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["uses"], "gh.issue")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["register"], "issue")

    def test_loads_step_if_field_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  enabled: true
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if: ${inputs.enabled}
                        uses: gh.issue
                      - name: remember
                        if: ${inputs.enabled}
                        state_set:
                          state.task_memory[inputs.enabled].flag: ${inputs.enabled}
                """
            )
        )

        self.assertEqual(workflow.steps[0].if_, "${inputs.enabled}")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["if"], "${inputs.enabled}")
        self.assertEqual(workflow.steps[1].if_, "${inputs.enabled}")

    def test_loads_step_launcher_field_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        uses: shell.command
                        launcher: shell_frontend
                """
            )
        )

        self.assertEqual(workflow.steps[0].launcher, "shell_frontend")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["launcher"], "shell_frontend")

    def test_loads_value_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: compute-branch
                        value:
                          format: "{}/{}"
                          args:
                            - ${inputs.type | lower}
                            - ${inputs.issue_number}
                        register: branch
                """
            )
        )

        self.assertEqual(workflow.steps[0].value, {"format": "{}/{}", "args": ["${inputs.type | lower}", "${inputs.issue_number}"]})
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["register"], "branch")

    def test_loads_expr_guard_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards:
                      - git.worktree.clean and git.branch != "main"
                  - steps: []
                """
            )
        )

        self.assertEqual(workflow.guards[0].expr, 'git.worktree.clean and git.branch != "main"')
        self.assertEqual(workflow.to_contract()["blocks"][0]["guards"][0], 'git.worktree.clean and git.branch != "main"')

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

    def test_loads_profile_launchers_into_typed_model(self) -> None:
        profile = load_profile_text(
            textwrap.dedent(
                """
                name: backend-default
                launchers:
                  shell_frontend:
                    connector: shell.command
                    before: export NVM_DIR="$HOME/.nvm"
                    after: "true"
                """
            )
        )

        self.assertEqual(profile.launchers["shell_frontend"].connector, "shell.command")
        self.assertEqual(profile.to_contract()["launchers"]["shell_frontend"]["before"], 'export NVM_DIR="$HOME/.nvm"')

    def test_loads_profile_launcher_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            profile_path = root / "frontend.yml"
            launcher_dir = root / "launchers"
            launcher_dir.mkdir()
            (launcher_dir / "shell-front.yml").write_text(
                "connector: shell.command\nbefore: nvm use\nafter: \"true\"\n",
                encoding="utf-8",
            )
            profile_path.write_text(
                textwrap.dedent(
                    """
                    name: frontend
                    launchers:
                      shell_frontend:
                        file: launchers/shell-front.yml
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            profile = load_profile_file(profile_path)

        self.assertEqual(profile.launchers["shell_frontend"].before, "nvm use")

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

    def test_load_workflow_file_expands_includes_relative_to_including_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            blocks_dir = root / "blocks"
            blocks_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: blocks/guard-block
                      - include: blocks/step-block
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (blocks_dir / "guard-block.yaml").write_text("guards: []\n", encoding="utf-8")
            (blocks_dir / "step-block.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: inspect
                        uses: gh.issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(len(workflow.blocks), 2)
        self.assertEqual(workflow.steps[0].name, "inspect")

    def test_load_workflow_file_stops_on_first_matching_include_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            launch_dir = root / "launch"
            workflow_dir = root / "workflows"
            launch_dir.mkdir()
            workflow_dir.mkdir()
            workflow_path = workflow_dir / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: shared/block
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (workflow_dir / "shared").mkdir()
            (launch_dir / "shared").mkdir()
            (workflow_dir / "shared" / "block.yaml").write_text("guards: []\n", encoding="utf-8")
            (launch_dir / "shared" / "block.yaml").write_text("steps: []\n", encoding="utf-8")

            workflow = load_workflow_file(workflow_path, launch_dir=launch_dir)

        self.assertEqual(len(workflow.guards), 0)
        self.assertEqual(len(workflow.steps), 0)
        self.assertEqual(workflow.to_contract()["blocks"][0], {"guards": []})

    def test_load_workflow_file_rejects_include_cycles_with_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: shared/a
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "shared").mkdir()
            (root / "shared" / "a.yaml").write_text("include: b\n", encoding="utf-8")
            (root / "shared" / "b.yaml").write_text("include: a\n", encoding="utf-8")

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        diagnostic = context.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "load.workflow.include.cycle")
        self.assertEqual(
            [Path(item).name for item in diagnostic.details["include_chain"]],
            ["workflow.yaml", "a.yaml", "b.yaml", "a.yaml"],
        )

    def test_load_workflow_file_rejects_upward_include_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: ../outside
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        diagnostic = context.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "load.workflow.include.forbidden_path")

    def test_load_workflow_file_rejects_non_file_include_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: shared/block
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "shared").mkdir()
            (root / "shared" / "block.yaml").mkdir()

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        diagnostic = context.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "load.workflow.include.not_file")

    def test_load_workflow_file_rejects_include_depth_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: shared/0
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            shared = root / "shared"
            shared.mkdir()
            for index in range(33):
                target = f"{index + 1}" if index < 32 else "end"
                (shared / f"{index}.yaml").write_text(f'include: "{target}"\n', encoding="utf-8")
            (shared / "end.yaml").write_text("guards: []\n", encoding="utf-8")

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        diagnostic = context.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "load.workflow.include.depth")

    def test_load_workflow_file_allows_repeated_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: shared/guard-block
                      - include: shared/guard-block
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "shared").mkdir()
            (root / "shared" / "guard-block.yaml").write_text("guards: []\n", encoding="utf-8")

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(len(workflow.blocks), 2)
        self.assertEqual(workflow.to_contract()["blocks"], [{"guards": []}, {"guards": []}])


if __name__ == "__main__":
    unittest.main()
