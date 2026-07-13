import contextlib
import io
import json
import os
import tempfile
import textwrap
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from ordo.cli import main as cli_main
from ordo.model.runtime import ExecutionPlan, Mode, RuntimeResult, RuntimeStatus
from ordo.runtime import check_workflow
from ordo.playbook import PlaybookError, activate_playbook, activated_working_directory, discover_playbook_path

from tests.support import STANDARD_CONNECTOR_PROVIDER


class PlaybookActivationTest(unittest.TestCase):
    def test_discover_playbook_missing_returns_structured_discovery_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PlaybookError) as ctx:
                discover_playbook_path(cwd=temp_dir)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.discovery.missing")
        self.assertEqual(diagnostic.details["category"], "discovery")
        self.assertEqual(diagnostic.details["stage"], "activation")

    def test_activate_playbook_reports_missing_workflow_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                "version: 1\nworkflows: {}\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="missing", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.workflow.missing")
        self.assertEqual(diagnostic.details["category"], "workflow")
        self.assertEqual(diagnostic.path, ("workflows", "missing"))

    def test_activate_playbook_reports_missing_profile_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  source: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", profile_name="review", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.profile.missing")
        self.assertEqual(diagnostic.details["category"], "profile")
        self.assertEqual(diagnostic.path, ("profiles", "review"))

    def test_activate_playbook_explicit_profile_overrides_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: backend-default
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend-default:
                        file: backend-default.yml
                      review:
                        file: review.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  source: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend-default.yml").write_text(
                "name: backend-default\ninputs: {source: default}\nchecks: []\noverrides: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "review.yml").write_text(
                "name: review\ninputs: {source: explicit}\nchecks: []\noverrides: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="review", cwd=root)

        self.assertEqual(activated.profile.name if activated.profile else None, "review")
        self.assertEqual(activated.profile.inputs["source"], "explicit")

    def test_activate_playbook_loads_profile_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "launchers").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "launchers" / "shell-front.yml").write_text(
                "connector: shell.command\nbefore: nvm use\nafter: \"true\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text(
                textwrap.dedent(
                    """
                    name: frontend
                    inputs: {}
                    checks: []
                    overrides: []
                    launchers:
                      shell_frontend:
                        file: ../launchers/shell-front.yml
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="frontend", cwd=root)

        self.assertEqual(activated.profile.launchers["shell_frontend"].connector, "shell.command")

    def test_activate_playbook_applies_launch_time_input_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      review:
                        file: review.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      source: workflow
                      keep: true
                      region: {}
                      enabled: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "review.yml").write_text(
                textwrap.dedent(
                    """
                    name: review
                    inputs:
                      source: profile
                      region: us
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="inspect-issue",
                profile_name="review",
                input_overrides={"source": "cli", "enabled": True},
                cwd=root,
            )

        self.assertEqual(activated.workflow.inputs["source"], "cli")
        self.assertEqual(activated.workflow.inputs["enabled"], True)
        self.assertEqual(activated.workflow.inputs["keep"], True)
        self.assertNotIn("source", activated.profile.inputs if activated.profile is not None else {})
        self.assertEqual(activated.profile.inputs["region"], "us")

    def test_activate_playbook_requires_all_declared_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository:
                        description: repo
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.workflow.input_missing")

    def test_activate_playbook_rejects_unknown_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository:
                        description: repo
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", input_overrides={"repository": "owner/repo", "extra": True}, cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.workflow.input_unknown")

    def test_activate_playbook_accepts_empty_string_and_null_as_present_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      body:
                        description: body text
                      assignee:
                        description: nullable owner
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="inspect-issue",
                input_overrides={"body": "", "assignee": None},
                cwd=root,
            )

        self.assertEqual(activated.workflow.inputs["body"], "")
        self.assertIsNone(activated.workflow.inputs["assignee"])

    def test_activate_playbook_validates_assembled_workflow_after_include_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository:
                        description: repo
                    blocks:
                      - include: fragments/inspect
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "fragments").mkdir()
            (root / ".ordo" / "workflows" / "fragments" / "inspect.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          repository: ${inputs.repository}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", input_overrides={"repository": "owner/repo"}, cwd=root)

        self.assertEqual(activated.workflow.steps[0].operation.with_["repository"], "${inputs.repository}")

    def test_activate_playbook_reports_validation_errors_after_include_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    blocks:
                      - include: fragments/inspect
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "fragments").mkdir()
            (root / ".ordo" / "workflows" / "fragments" / "inspect.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: inspect
                        uses: gh.issue
                        unexpected: true
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "validation.unknown_field")
        self.assertEqual(ctx.exception.diagnostics[0].path, ("blocks", "0", "steps", "0", "unexpected"))

    def test_activate_playbook_resolves_working_directory_relative_to_playbook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ../repo
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)
            self.assertEqual(activated.working_directory, (root / "repo").resolve())

    def test_activate_playbook_reports_missing_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ../missing
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

            diagnostic = ctx.exception.diagnostics[0]
            self.assertEqual(diagnostic.code, "playbook.workflow.working_directory_missing")
            self.assertEqual(diagnostic.path, ("workflows", "inspect-issue", "working_directory"))

    def test_activate_playbook_resolves_working_directory_from_input_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo-a").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ${inputs.repo_dir}
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repo_dir: ../repo-a\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-a").resolve())

    def test_activate_playbook_resolves_working_directory_from_profile_input_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo-b").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: review
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ${inputs.repo_dir}
                    profiles:
                      review:
                        file: review.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repo_dir: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "review.yml").write_text(
                "name: review\ninputs:\n  repo_dir: ../repo-b\nchecks: []\noverrides: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-b").resolve())

    def test_activate_playbook_uses_defaults_working_directory_when_more_specific_levels_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo-default").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      working_directory: ../repo-default
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-default").resolve())

    def test_activate_playbook_profile_working_directory_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo-default").mkdir()
            (root / "repo-profile").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: review
                      working_directory: ../repo-default
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      review:
                        file: review.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "review.yml").write_text(
                "name: review\nworking_directory: ../repo-profile\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-profile").resolve())

    def test_activate_playbook_workflow_working_directory_overrides_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo-profile").mkdir()
            (root / "repo-workflow").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: review
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ../repo-workflow
                    profiles:
                      review:
                        file: review.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "review.yml").write_text(
                "name: review\nworking_directory: ../repo-profile\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-workflow").resolve())

    def test_activate_playbook_loads_profile_switch_context_when_workflow_uses_runtime_profile_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo-a").mkdir()
            (root / "repo-b").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: frontend
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repo_dir: {}\nblocks:\n  - steps:\n      - name: switch\n        uses: runtime.profile.use\n        with:\n          profile: backend\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text(
                "name: frontend\ninputs:\n  repo_dir: ../repo-a\nworking_directory: ${inputs.repo_dir}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repo_dir: ../repo-b\nworking_directory: ${inputs.repo_dir}\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            assert activated.available_profiles is not None
            assert activated.profile_working_directories is not None
            self.assertIn("frontend", activated.available_profiles)
            self.assertIn("backend", activated.available_profiles)
            self.assertEqual(activated.profile_working_directories["frontend"], (root / "repo-a").resolve())
            self.assertEqual(activated.profile_working_directories["backend"], (root / "repo-b").resolve())

    def test_activate_playbook_prepends_pre_run_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - workflows/resolve-context.yml
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "steps:\n  - name: prepare\n    value: ok\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - steps:\n      - name: main\n        value: done\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            first_step = activated.workflow.steps[0]
            self.assertEqual(first_step.name, "pre_run[0]")
            self.assertEqual(first_step.run, "workflows/resolve-context.yml")
            self.assertEqual(first_step.resolved_run_path, str((root / ".ordo" / "workflows" / "resolve-context.yml").resolve()))

    def test_check_after_activation_marks_pre_run_main_guard_gap_as_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - workflows/resolve-context.yml
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "steps:\n  - name: prepare\n    value: ok\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      enabled: {}
                    blocks:
                      - guards:
                          - inputs.enabled == true
                      - steps:
                          - name: main
                            value: done
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", input_overrides={"enabled": True}, cwd=root)
            result = check_workflow(activated.workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "unknown")
            self.assertFalse(result.outputs["analysis_complete"])
            self.assertIn("relevant_guard_coverage_incomplete", result.outputs["incomplete_reasons"])
            self.assertIn("pre_run_precedes_main_guard_coverage", result.outputs["incomplete_reasons"])

    def test_activate_playbook_resolves_working_directory_from_input_override_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo-c").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ${inputs.repo_dir}
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repo_dir: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", input_overrides={"repo_dir": "../repo-c"}, cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo-c").resolve())

    def test_activate_playbook_rejects_state_reference_in_working_directory_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ${state.task_memory[inputs.issue_ref].branch}
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  issue_ref: demo\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

            diagnostic = ctx.exception.diagnostics[0]
            self.assertEqual(diagnostic.code, "playbook.workflow.working_directory_expression_state_forbidden")

    def test_activate_playbook_rejects_step_reference_in_working_directory_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        working_directory: ${step.prepare.outputs.path}
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

            diagnostic = ctx.exception.diagnostics[0]
            self.assertEqual(diagnostic.code, "playbook.workflow.working_directory_expression_step_forbidden")

    def test_activated_working_directory_changes_process_cwd_temporarily(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "repo"
            target.mkdir()
            original = Path.cwd()
            activated = SimpleNamespace(working_directory=target)

            with activated_working_directory(activated):
                self.assertEqual(Path.cwd(), target)

            self.assertEqual(Path.cwd(), original)

    def test_activate_playbook_rejects_workflow_entry_profile_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        profile: backend-default
                    profiles:
                      backend-default:
                        file: backend-default.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.workflow.profile_field_forbidden")
        self.assertEqual(diagnostic.details["category"], "workflow")
        self.assertEqual(diagnostic.path, ("workflows", "inspect-issue", "profile"))

    def test_activate_playbook_reports_missing_profile_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: backend-default
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend-default:
                        file: backend-default.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.profile.file_missing")
        self.assertEqual(diagnostic.details["category"], "profile")

    def test_activate_playbook_reports_missing_state_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      close-task:
                        file: close-task.yml
                    profiles: {}
                    states:
                      repo_task_state:
                        path: .ordo/state/task-state.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: close-task
                    state_needs:
                      task_memory: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="close-task", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.state_binding.missing")
        self.assertEqual(diagnostic.details["category"], "state_binding")

    def test_activate_playbook_reports_unknown_state_binding_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      close-task:
                        file: close-task.yml
                        state_bindings:
                          task_memory: repo_task_state
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: close-task
                    state_needs:
                      task_memory: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="close-task", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.state_binding.target_missing")
        self.assertEqual(diagnostic.details["category"], "state_binding")

    def test_activate_playbook_reports_extra_state_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      close-task:
                        file: close-task.yml
                        state_bindings:
                          task_memory: repo_task_state
                          extra_memory: repo_task_state
                    profiles: {}
                    states:
                      repo_task_state:
                        path: .ordo/state/task-state.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: close-task
                    state_needs:
                      task_memory: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="close-task", cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.state_binding.extra")
        self.assertEqual(diagnostic.details["category"], "state_binding")

    def test_activate_playbook_resolves_state_needs_without_rewriting_workflow_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    states:
                      repo_task_state:
                        path: .ordo/state/task-state.json
                    defaults:
                      profile: backend-default
                    workflows:
                      close-task:
                        file: close-task.yml
                        state_bindings:
                          task_memory: repo_task_state
                    profiles:
                      backend-default:
                        file: backend-default.yml
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: close-task
                    inputs:
                      issue_ref: owner/repo#1
                      branch: feature/demo
                    state_needs:
                      task_memory: {}
                    blocks:
                      - guards: []
                      - steps:
                          - name: remember-branch
                            state_set:
                              state.task_memory[inputs.issue_ref].branch: ${inputs.branch}
                          - name: forget-branch
                            state_delete: state.task_memory[inputs.issue_ref].branch
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend-default.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend-default
                    inputs: {}
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="close-task", cwd=root)

            self.assertEqual(activated.workflow.workflow, "close-task")
            self.assertEqual(activated.profile.name if activated.profile else None, "backend-default")
            state_path = activated.workflow.states["repo_task_state"]
            self.assertTrue(str(state_path).endswith(os.path.join(".ordo", "state", "task-state.json")))
            self.assertEqual(activated.workflow.state_bindings, {"task_memory": "repo_task_state"})
            self.assertEqual(
                [diagnostic.code for diagnostic in activated.diagnostics],
                ["playbook.workflow.working_directory_recommended_for_state"],
            )
            self.assertEqual(
                activated.workflow.steps[0].state_set,
                {"state.task_memory[inputs.issue_ref].branch": "${inputs.branch}"},
            )
            self.assertEqual(
                activated.workflow.steps[1].state_delete,
                "state.task_memory[inputs.issue_ref].branch",
            )

    def test_activate_playbook_resolves_relative_state_paths_from_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo").mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    states:
                      repo_task_state:
                        path: .ordo/state/task-state.json
                    workflows:
                      close-task:
                        file: close-task.yml
                        working_directory: ../repo
                        state_bindings:
                          task_memory: repo_task_state
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: close-task
                    state_needs:
                      task_memory: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="close-task", cwd=root)

            self.assertEqual(activated.working_directory, (root / "repo").resolve())
            self.assertEqual(activated.diagnostics, ())
            self.assertEqual(
                activated.workflow.states["repo_task_state"],
                str((root / "repo" / ".ordo" / "state" / "task-state.json").resolve()),
            )

    def test_cli_plan_mode_runs_through_playbook_activation_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "plan"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["workflow"], "inspect-issue")

    def test_cli_runs_mode_inside_activated_working_directory(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/playbook.yml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=Path("/tmp"),
        )
        runtime_result = RuntimeResult(
            mode=Mode.PLAN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={},
        )
        observed: dict[str, str] = {}
        original = Path.cwd()

        def fake_run_mode(_mode, _workflow, _profile):
            observed["cwd"] = os.getcwd()
            return runtime_result

        with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "plan"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", side_effect=fake_run_mode):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed["cwd"], "/tmp")
        self.assertEqual(Path.cwd(), original)

    def test_cli_activation_error_uses_resolution_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "plan", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "activation")
            self.assertEqual(payload["status"], "resolution_error")
            self.assertEqual(payload["diagnostics"][0]["code"], "playbook.discovery.missing")
            self.assertEqual(payload["diagnostics"][0]["details"]["category"], "discovery")

    def test_cli_run_mode_is_temporarily_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "run", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "run")
            self.assertEqual(payload["status"], "execution_error")
            self.assertEqual(payload["diagnostics"][0]["code"], "playbook.run.disabled")

    def test_cli_passes_input_overrides_to_playbook_activation(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/playbook.yml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
        )
        runtime_result = RuntimeResult(
            mode=Mode.PLAN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={},
        )

        with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "--input", "enabled=true", "--input", "count=3", "plan"]):
            with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(activate_mock.call_args.kwargs["input_overrides"], {"enabled": True, "count": 3})

    def test_cli_passes_input_file_overrides_to_playbook_activation(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/playbook.yml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
        )
        runtime_result = RuntimeResult(
            mode=Mode.PLAN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            body_path = Path(temp_dir) / "body.md"
            body_path.write_text("line 1\nline 2\n", encoding="utf-8")

            with patch(
                "sys.argv",
                [
                    "ordo-playbook",
                    "--workflow",
                    "inspect-issue",
                    "--input",
                    "enabled=true",
                    "--input-file",
                    f"body={body_path}",
                    "plan",
                ],
            ):
                with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                    with patch("ordo.cli._run_mode", return_value=runtime_result):
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            activate_mock.call_args.kwargs["input_overrides"],
            {"enabled": True, "body": "line 1\nline 2\n"},
        )

    def test_cli_input_file_override_wins_over_inline_input_for_same_key(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/playbook.yml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
        )
        runtime_result = RuntimeResult(
            mode=Mode.PLAN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            body_path = Path(temp_dir) / "body.md"
            body_path.write_text("file value\n", encoding="utf-8")

            with patch(
                "sys.argv",
                [
                    "ordo-playbook",
                    "--workflow",
                    "inspect-issue",
                    "--input",
                    "body=inline",
                    "--input-file",
                    f"body={body_path}",
                    "plan",
                ],
            ):
                with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                    with patch("ordo.cli._run_mode", return_value=runtime_result):
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(activate_mock.call_args.kwargs["input_overrides"], {"body": "file value\n"})


if __name__ == "__main__":
    unittest.main()
