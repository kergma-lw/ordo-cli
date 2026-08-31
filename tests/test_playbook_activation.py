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
from ordo.model.diagnostic import Diagnostic
from ordo.model.profile import Profile
from ordo.model.runtime import ExecutionPlan, Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import check_workflow, execute_workflow, explain_workflow, plan_workflow
from ordo.playbook import PlaybookError, WorkflowCatalogInput, activate_playbook, activated_working_directory, discover_playbook_path, inspect_playbook_workflow
from ordo.runtime.profiles import apply_profile_defaults_to_subsequent_steps

from tests.support import STANDARD_CONNECTOR_PROVIDER


class PlaybookActivationTest(unittest.TestCase):
    def test_activate_playbook_records_explicit_input_keys_on_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend:
                        file: backend.yml
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
                      repository: {}
                      issue_number: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles").mkdir()
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repository: owner/backend
                      repo_kind: backend
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="inspect-issue",
                profile_name="backend",
                input_overrides={"issue_number": 42, "repository": "override/repo"},
                cwd=root,
            )

        self.assertEqual(activated.workflow.explicit_input_keys, ("issue_number", "repository"))

    def test_activate_playbook_applies_workflow_entry_with_before_cli_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: entry/repo
                          issue_number: 7
                    profiles:
                      backend:
                        file: backend.yml
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
                      repository: {}
                      issue_number: {}
                    blocks:
                      - guards: []
                      - steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repository: profile/repo\n  issue_number: 5\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="inspect-issue",
                profile_name="backend",
                input_overrides={"repository": "cli/repo"},
                cwd=root,
            )

        self.assertEqual(activated.workflow.inputs["repository"], "cli/repo")
        self.assertEqual(activated.workflow.inputs["issue_number"], 7)

    def test_activate_playbook_passes_pre_run_with_into_pre_run_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/resolve-context.yml
                        with:
                          active_profile_key: active_profile
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "version: 0\nworkflow: resolve-context\ninputs:\n  active_profile_key: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

        pre_run_step = activated.workflow.blocks[0].steps[0]
        self.assertEqual(pre_run_step.run_inputs, {"active_profile_key": "active_profile"})

    def test_inspect_playbook_workflow_exposes_playbook_owned_with_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: owner/repo
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            entry = inspect_playbook_workflow("inspect-issue", cwd=root)

        self.assertEqual(entry.with_, {"repository": "owner/repo"})

    def test_inspect_playbook_workflow_exposes_caller_inputs_from_null_with_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: owner/repo
                          issue_number:
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  issue_number: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            entry = inspect_playbook_workflow("inspect-issue", cwd=root)

        self.assertEqual(entry.with_, {"repository": "owner/repo"})
        self.assertEqual(entry.caller_inputs, ("issue_number",))

    def test_activate_playbook_requires_caller_inputs_declared_via_null_with_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: owner/repo
                          issue_number:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  issue_number: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

            activated = activate_playbook(workflow_name="inspect-issue", input_overrides={"issue_number": 42}, cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.workflow.input_missing")
        self.assertEqual(ctx.exception.diagnostics[0].details["declared_inputs"], ("repository", "issue_number"))
        self.assertEqual(ctx.exception.diagnostics[0].details["missing_inputs"], ["issue_number"])
        self.assertEqual(activated.workflow.inputs["repository"], "owner/repo")
        self.assertEqual(activated.workflow.inputs["issue_number"], 42)

    def test_activate_playbook_allows_nested_profile_switch_to_replace_profile_context_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: meta
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          workspace_profiles: [backend]
                    profiles:
                      meta:
                        file: meta.yml
                      backend:
                        file: backend.yml
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
                      workspace_profiles: []
                      repo_kind: {}
                      repo_dir: {}
                      repository: {}
                    blocks:
                      - steps:
                          - name: fan
                            for_each: inputs.workspace_profiles
                            steps:
                              - name: switch
                                profile_switch: ${item}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "meta.yml").write_text(
                "name: meta\ninputs:\n  repo_kind: meta\n  repo_dir: /tmp/meta\n  repository: owner/meta\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repo_kind: backend\n  repo_dir: /tmp/backend\n  repository: owner/backend\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.diagnostics, ())

    def test_apply_profile_defaults_to_subsequent_steps_preserves_explicit_input_keys(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="inspect-issue",
            inputs={"repository": "override/repo", "issue_number": 42},
            declared_inputs={"repository": {}, "issue_number": {}, "profile": {}},
            explicit_input_keys=("repository",),
            blocks=(),
        )
        profile = Profile(name="backend", inputs={"repository": "owner/backend", "project_id": "PVT_demo"})

        applied = apply_profile_defaults_to_subsequent_steps(workflow, profile)

        self.assertTrue(applied.ok)
        assert applied.workflow is not None
        self.assertEqual(applied.workflow.explicit_input_keys, ("repository",))

    def test_discover_playbook_missing_returns_structured_discovery_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PlaybookError) as ctx:
                discover_playbook_path(cwd=temp_dir)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.discovery.missing")
        self.assertEqual(diagnostic.details["category"], "discovery")
        self.assertEqual(diagnostic.details["stage"], "activation")
        self.assertIn(".ordo/ordo.yaml", diagnostic.message)

    def test_discover_playbook_does_not_fall_back_to_legacy_playbook_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "playbook.yml").write_text("version: 1\nworkflows: {}\nprofiles: {}\nstates: {}\n", encoding="utf-8")
            (root / ".ordo" / "playbook.yaml").write_text("version: 1\nworkflows: {}\nprofiles: {}\nstates: {}\n", encoding="utf-8")

            with self.assertRaises(PlaybookError) as ctx:
                discover_playbook_path(cwd=root)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "playbook.discovery.missing")
        self.assertEqual(diagnostic.details["expected_path"], str(root / ".ordo" / "ordo.yaml"))

    def test_activate_playbook_reports_missing_workflow_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
        self.assertEqual(activated.workflow.launch_profile_name, "review")
        self.assertEqual(activated.workflow.launch_profile_source, "explicit_cli")

    def test_check_after_activation_explicit_cli_profile_wins_over_pre_run_profile_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "meta"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend:
                        file: backend.yml
                      meta:
                        file: meta.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  active_profile_key: active_profile\n  repository: {}\nblocks:\n  - guards:\n      - inputs.repository == \"kergma-lw/checklist-backend\"\n  - steps:\n      - name: main\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repository: kergma-lw/checklist-backend\n  repo_dir: /tmp/backend\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "meta.yml").write_text(
                "name: meta\ninputs:\n  repository: kergma-lw/checklist-meta\n  repo_dir: /tmp/meta\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="backend", cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "backend")
        self.assertIsNone(result.failed_guard)
        self.assertNotIn('kergma-lw/checklist-meta', json.dumps(result.outputs, ensure_ascii=False, sort_keys=True))

    def test_activate_playbook_merges_playbook_and_profile_connector_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    connectors:
                      git:
                        directory: /repos/default
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend:
                        file: backend.yml
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
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    connectors:
                      git:
                        worktree: linked
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="backend", cwd=root)

        self.assertEqual(activated.connector_contexts["git"]["directory"], "/repos/default")
        self.assertEqual(activated.connector_contexts["git"]["worktree"], "linked")
        self.assertEqual(activated.workflow.connector_contexts["git"]["directory"], "/repos/default")

    def test_activate_playbook_exposes_optional_workflow_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        description: Inspect one issue and prepare local context
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

        self.assertEqual(activated.workflow_description, "Inspect one issue and prepare local context")

    def test_activate_playbook_rejects_non_string_workflow_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        description:
                          - invalid
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
        self.assertEqual(diagnostic.code, "playbook.workflow.description_invalid")
        self.assertEqual(diagnostic.path, ("workflows", "inspect-issue", "description"))

    def test_activate_playbook_loads_profile_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "launchers").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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

    def test_activate_playbook_tracks_consumed_and_surplus_profile_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend:
                        file: backend.yml
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
                      repository: {}
                    blocks:
                      - steps:
                          - name: inspect
                            uses: gh.issue
                            with:
                              repository: ${inputs.repository}
                              issue_number: 7
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repository: acme/repo
                      repo_dir: /tmp/repo
                      repo_kind: backend
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", profile_name="backend", cwd=root)

        self.assertEqual(activated.input_analysis.relevant_inputs, ("repository",))
        self.assertEqual(activated.input_analysis.consumed_profile_inputs, ("repository",))
        self.assertEqual(activated.input_analysis.surplus_profile_inputs, ("repo_dir", "repo_kind"))

    def test_activate_playbook_tolerates_profile_surplus_inputs_when_workflow_does_not_consume_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      issue-view:
                        file: issue-view.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "issue-view.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: issue-view
                    inputs:
                      profile: {}
                      number: {}
                      repository: {}
                      project_id: {}
                    blocks:
                      - steps:
                          - name: load issue
                            uses: gh.issue
                            with:
                              repository: ${inputs.repository}
                              issue_number: ${inputs.number}
                          - name: load project item
                            uses: gh.project.issue
                            with:
                              repository: ${inputs.repository}
                              issue_number: ${inputs.number}
                              project_id: ${inputs.project_id}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repo_kind: backend
                      repo_dir: /tmp/backend
                      repository: acme/backend
                      project_id: PVT_demo
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            activated = activate_playbook(
                workflow_name="issue-view",
                profile_name="backend",
                input_overrides={"profile": "backend", "number": 42},
                cwd=root,
            )

        self.assertEqual(activated.workflow.inputs["repository"], "acme/backend")
        self.assertEqual(activated.workflow.inputs["project_id"], "PVT_demo")
        self.assertEqual(activated.input_analysis.surplus_profile_inputs, ("repo_dir", "repo_kind"))
        self.assertFalse(any(diagnostic.code == "playbook.profile.surplus_inputs_ignored" for diagnostic in activated.diagnostics))

    def test_cli_review_reaches_analysis_when_profile_supplies_surplus_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      issue-view:
                        file: issue-view.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "issue-view.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: issue-view
                    inputs:
                      profile: {}
                      number: {}
                      repository: {}
                      project_id: {}
                    blocks:
                      - steps:
                          - name: load issue
                            uses: gh.issue
                            with:
                              repository: ${inputs.repository}
                              issue_number: ${inputs.number}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repo_kind: backend
                      repo_dir: /tmp/backend
                      repository: acme/backend
                      project_id: PVT_demo
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with patch("sys.argv", [
                "ordo-playbook",
                "--file",
                str(root / ".ordo" / "ordo.yaml"),
                "--profile",
                "backend",
                "--input",
                "profile=backend",
                "--input",
                "number=42",
                "--json",
                "review",
                "issue-view",
            ]):
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "review")
        self.assertFalse(any(item["code"] == "playbook.profile.surplus_inputs_ignored" for item in payload["diagnostics"]))
        self.assertIn("findings", payload["outputs"])

    def test_cli_check_hides_expected_profile_surplus_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      issue-view:
                        file: issue-view.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "issue-view.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: issue-view
                    inputs:
                      profile: {}
                      number: {}
                      repository: {}
                      project_id: {}
                    blocks:
                      - guards:
                          - inputs.profile == "backend"
                          - inputs.number == 42
                      - steps:
                          - name: load issue
                            uses: gh.issue
                            with:
                              repository: ${inputs.repository}
                              issue_number: ${inputs.number}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repo_kind: backend
                      repo_dir: /tmp/backend
                      repository: acme/backend
                      project_id: PVT_demo
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with patch("sys.argv", [
                "ordo-playbook",
                "--file",
                str(root / ".ordo" / "ordo.yaml"),
                "--profile",
                "backend",
                "--input",
                "profile=backend",
                "--input",
                "number=42",
                "--json",
                "check",
                "issue-view",
            ]):
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "check")
        self.assertFalse(any(item["code"] == "playbook.profile.surplus_inputs_ignored" for item in payload["diagnostics"]))

    def test_cli_review_surfaces_static_format_diagnostic_before_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      issue-view:
                        file: issue-view.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "issue-view.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: issue-view
                    inputs:
                      profile: {}
                      number: {}
                      repository: {}
                      project_id: {}
                    blocks:
                      - guards:
                          - inputs.profile == "backend"
                          - inputs.number | is_integer
                      - steps:
                          - name: Publish issue view
                            publish:
                              issue_ref:
                                format: "%s#%s"
                                args:
                                  - ${inputs.repository}
                                  - ${inputs.number}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                textwrap.dedent(
                    """
                    name: backend
                    inputs:
                      repo_kind: backend
                      repo_dir: /tmp/backend
                      repository: acme/backend
                      project_id: PVT_demo
                    checks: []
                    overrides: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with patch("sys.argv", [
                "ordo-playbook",
                "--file",
                str(root / ".ordo" / "ordo.yaml"),
                "--profile",
                "backend",
                "--input",
                "profile=backend",
                "--input",
                "number=42",
                "--json",
                "review",
                "issue-view",
            ]):
                with contextlib.redirect_stdout(stdout):
                    exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertIn(payload["status"], {"validation_error", "resolution_error"})
        self.assertTrue(any(item["code"] == "validation.workflow.value_expr.format.placeholder_count" for item in payload["diagnostics"]))

    def test_activate_playbook_accepts_empty_string_and_null_as_present_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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

    def test_activate_playbook_reports_validation_errors_from_run_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
                      - steps:
                          - name: expand
                            run: fragments/inspect
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "fragments").mkdir()
            (root / ".ordo" / "workflows" / "fragments" / "inspect.yaml").write_text(
                textwrap.dedent(
                    """
                    blocks:
                      - guards:
                          - inputs.repository == "owner/repo"
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")

    def test_activate_playbook_resolves_working_directory_relative_to_playbook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo").mkdir()
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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

    def test_activate_playbook_loads_profile_switch_context_when_workflow_uses_profile_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo-a").mkdir()
            (root / "repo-b").mkdir()
            (root / ".ordo" / "ordo.yaml").write_text(
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
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repo_dir: {}\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: backend\n",
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
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/resolve-context.yml
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
                "steps:\n  - name: prepare\n    value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - steps:\n      - name: main\n        value: \"done\"\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", cwd=root)

            first_step = activated.workflow.steps[0]
            self.assertEqual(first_step.name, "pre_run[0]")
            self.assertEqual(first_step.run, "workflows/resolve-context.yml")
            self.assertEqual(first_step.resolved_run_path, str((root / ".ordo" / "workflows" / "resolve-context.yml").resolve()))
            self.assertEqual(first_step.run_state_bindings, {})

    def test_activate_playbook_applies_explicit_pre_run_state_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/resolve-context.yml
                        state_bindings:
                          shared_state: shared_state
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles: {}
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "steps:\n  - name: prepare\n    profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: main\n        value: \"done\"\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="inspect-issue", input_overrides={"active_profile_key": "active_profile"}, cwd=root)

            first_step = activated.workflow.steps[0]
            self.assertEqual(first_step.run_state_bindings, {"shared_state": "shared_state"})
            self.assertEqual(first_step.run_states, {"shared_state": str((root / ".ordo" / "repo.json").resolve())})

    def test_activate_playbook_rejects_pre_run_state_binding_target_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/resolve-context.yml
                        state_bindings:
                          shared_state: shared_state
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
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text("steps:\n  - name: prepare\n    value: \"ok\"\n", encoding="utf-8")
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - steps:\n      - name: main\n        value: \"done\"\n",
                encoding="utf-8",
            )

            with self.assertRaises(PlaybookError) as ctx:
                activate_playbook(workflow_name="inspect-issue", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "playbook.pre_run.state_binding_target_missing")

    def test_check_after_activation_marks_pre_run_main_guard_gap_as_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/resolve-context.yml
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
                "steps:\n  - name: prepare\n    value: \"ok\"\n",
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
                            value: "done"
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

    def test_check_after_activation_expands_profile_only_pre_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      set-active-profile:
                        file: set-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "set-active-profile.yml").write_text(
                "version: 0\nworkflow: set-active-profile\ninputs:\n  profile: {}\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nblocks:\n  - guards:\n      - inputs.profile == \"backend\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="set-active-profile", input_overrides={"profile": "backend"}, cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertTrue(result.outputs["analysis_complete"])
            self.assertEqual(result.outputs["evaluated_relevant_guard_count"], 1)

    def test_check_after_activation_crosses_profile_only_pre_run_for_close_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      close-task:
                        file: close-task.yml
                        state_bindings:
                          shared_state: shared_state
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                "version: 0\nworkflow: close-task\ninputs:\n  active_profile_key: active_profile\n  repo_kind: {}\nstate_needs:\n  shared_state: {}\nblocks:\n  - guards:\n      - inputs.repo_kind == \"backend\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\ninputs:\n  repo_kind: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\ninputs:\n  repo_kind: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="close-task", cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertGreater(result.outputs["evaluated_relevant_guard_count"], 0)
            self.assertNotIn("pre_run_precedes_main_guard_coverage", result.outputs.get("incomplete_reasons", []))

    def test_check_after_activation_crosses_profile_only_pre_run_without_main_shared_state_need(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      set-task-size:
                        file: set-task-size.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "set-task-size.yml").write_text(
                "version: 0\nworkflow: set-task-size\ninputs:\n  active_profile_key: active_profile\n  repo_kind: {}\nblocks:\n  - guards:\n      - inputs.repo_kind == \"backend\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\ninputs:\n  repo_kind: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\ninputs:\n  repo_kind: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="set-task-size", cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertTrue(result.outputs["analysis_complete"])
            self.assertNotIn("profile_switch_not_resolvable_from_current_knowledge", result.outputs.get("incomplete_reasons", []))

    def test_check_after_activation_crosses_pre_run_profile_switch_via_nested_let_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: frontend
                    workflows:
                      set-task-size:
                        file: set-task-size.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "set-task-size.yml").write_text(
                "version: 0\nworkflow: set-task-size\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - guards:\n      - inputs.active_profile_key == \"active_profile\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="set-task-size", cwd=root)
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertTrue(result.outputs["analysis_complete"])
            self.assertEqual(result.outputs["active_profile"], "backend")
            self.assertNotIn("profile_switch_not_resolvable_from_current_knowledge", result.outputs.get("incomplete_reasons", []))
            self.assertNotIn("pre_run_precedes_main_guard_coverage", result.outputs.get("incomplete_reasons", []))

    def test_plan_after_activation_crosses_playbook_owned_pre_run_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      set-task-size:
                        file: set-task-size.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "set-task-size.yml").write_text(
                "version: 0\nworkflow: set-task-size\ninputs:\n  active_profile_key: active_profile\n  repo_kind: {}\nblocks:\n  - guards:\n      - inputs.repo_kind == \"backend\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\ninputs:\n  repo_kind: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\ninputs:\n  repo_kind: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="set-task-size", cwd=root)
            result = plan_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["allowed_state"], "allowed")
            self.assertTrue(result.outputs["analysis_complete"])

    def test_execute_after_activation_crosses_playbook_owned_pre_run_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      set-task-size:
                        file: set-task-size.yml
                    profiles:
                      frontend:
                        file: frontend.yml
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "set-task-size.yml").write_text(
                "version: 0\nworkflow: set-task-size\ninputs:\n  active_profile_key: active_profile\n  repo_kind: {}\nblocks:\n  - guards:\n      - inputs.repo_kind == \"backend\"\n  - steps:\n      - name: remember\n        value: \"ok\"\n        register: marker\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text("name: frontend\ninputs:\n  repo_kind: frontend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\ninputs:\n  repo_kind: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="set-task-size", cwd=root)
            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertIn("remember", result.outputs["executed_steps"])

    def test_check_after_activation_workflow_profile_overrides_pre_run_switched_repository_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / "repo.json").write_text('{"active_profile": "mobile", "active_story_issue_number": 99}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: meta
                    workflows:
                      story-get-task-for-work:
                        file: story-get-task-for-work.yml
                        state_bindings:
                          shared_state: shared_state
                    profiles:
                      mobile:
                        file: mobile.yml
                      meta:
                        file: meta.yml
                    states:
                      shared_state:
                        path: ../repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nstate_needs:\n  shared_state: {}\nlet:\n  active_profile: state.shared_state[inputs.active_profile_key]\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: active_profile\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "story-get-task-for-work.yml").write_text(
                "version: 0\nworkflow: story-get-task-for-work\nprofile: meta\ninputs:\n  repository: {}\n  project_id: {}\nstate_needs:\n  shared_state: {}\nlet:\n  active_story_issue_number: state.shared_state[\"active_story_issue_number\"]\nblocks:\n  - guards:\n      - active_story_issue_number | is_integer\n      - inputs.repository == \"kergma-lw/checklist-meta\"\n  - steps:\n      - name: remember\n        value: inputs.repository\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "mobile.yml").write_text(
                "name: mobile\ninputs:\n  repository: kergma-lw/checklist-mobile\n  project_id: mobile-project\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "meta.yml").write_text(
                "name: meta\ninputs:\n  repository: kergma-lw/checklist-meta\n  project_id: meta-project\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="story-get-task-for-work", cwd=root)
            self.assertEqual(activated.workflow.profile, "meta")
            result = check_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "meta")
            self.assertEqual(result.outputs["workflow_profile_declared"], "meta")
            self.assertIsNone(result.failed_guard)
            self.assertNotIn('kergma-lw/checklist-mobile', json.dumps(result.outputs, ensure_ascii=False, sort_keys=True))

            plan_result = plan_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )
            explain_result = explain_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(plan_result.status, RuntimeStatus.OK)
            self.assertEqual(plan_result.outputs["active_profile"], "meta")
            self.assertEqual(plan_result.outputs["active_profile_source"], "workflow")
            self.assertNotIn('kergma-lw/checklist-mobile', json.dumps(plan_result.outputs, ensure_ascii=False, sort_keys=True))

            self.assertEqual(explain_result.status, RuntimeStatus.OK)
            self.assertEqual(explain_result.outputs["active_profile"], "meta")

    def test_execute_after_activation_restores_parent_profile_after_nested_workflow_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    defaults:
                      profile: backend
                    workflows:
                      parent:
                        file: parent.yml
                    profiles:
                      backend:
                        file: backend.yml
                      meta:
                        file: meta.yml
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "parent.yml").write_text(
                "version: 0\nworkflow: parent\nblocks:\n  - steps:\n      - name: run-child\n        run: child.yml\n      - name: switch-backend\n        profile_switch: \"backend\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "child.yml").write_text(
                "version: 0\nworkflow: child\nprofile: meta\nblocks:\n  - steps:\n      - name: remember\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\n", encoding="utf-8")
            (root / ".ordo" / "profiles" / "meta.yml").write_text("name: meta\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="parent", cwd=root)
            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "backend")

    def test_execute_after_activation_accumulates_pre_run_results_before_main_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      publish:
                        file: publish.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: publish-pre\n        publish:\n          summary: \"pre\"\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "publish.yml").write_text(
                "version: 0\nworkflow: publish\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: publish-main\n        publish:\n          summary: \"main\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\n", encoding="utf-8")

            activated = activate_playbook(workflow_name="publish", cwd=root)
            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(list(result.published), [{"summary": "pre"}, {"summary": "main"}])

    def test_activate_playbook_resolves_working_directory_from_input_override_expression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / "repo-c").mkdir()
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            (root / ".ordo" / "ordo.yaml").write_text(
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
            with patch("sys.argv", ["ordo-playbook", "plan", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["workflow"], "inspect-issue")

    def test_cli_plan_mode_accepts_positional_workflow_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "plan", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["workflow"], "inspect-issue")

    def test_cli_modes_accept_positional_workflow_name_for_dispatch(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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

        for mode in ("review", "check", "plan", "explain"):
            with self.subTest(mode=mode):
                with patch("sys.argv", ["ordo-playbook", mode, "inspect-issue"]):
                    with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                        with patch("ordo.cli._run_mode", return_value=runtime_result) as run_mode_mock:
                            stdout = io.StringIO()
                            stderr = io.StringIO()
                            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                                exit_code = cli_main()

                self.assertEqual(exit_code, 0)
                self.assertEqual(activate_mock.call_args.kwargs["workflow_name"], "inspect-issue")
                self.assertEqual(run_mode_mock.call_args.args[0], mode)

    def test_cli_next_accepts_no_workflow_name(self) -> None:
        entry = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow_description="Inspect issue context",
            workflow_category="inspect",
            workflow_when="Use when context is missing",
            working_directory=None,
        )
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )

        with patch("sys.argv", ["ordo-playbook", "next", "--json"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(entry,)) as list_mock:
                with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                    with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "next")
        self.assertEqual(payload["scope"], "playbook")
        self.assertEqual(payload["best_candidate"]["workflow"], "inspect-issue")
        list_mock.assert_called_once()
        activate_mock.assert_called_once_with(
            workflow_name="inspect-issue",
            profile_name=None,
            input_overrides={},
            playbook_path=None,
        )

    def test_cli_next_rejects_workflow_argument(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next", "close-task"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main()

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("next does not accept a workflow name", stderr.getvalue())

    def test_cli_run_mode_accepts_positional_workflow_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["results"], [{"summary": "Workflow completed with no explicit result or published output."}])

    def test_cli_reports_missing_workflow_for_execution_command(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "plan"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main()

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("plan requires a workflow name", stderr.getvalue())

    def test_cli_next_does_not_require_workflow_name(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        entry = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow_description=None,
            workflow_category=None,
            workflow_when=None,
            working_directory=None,
        )
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )
        with patch("sys.argv", ["ordo-playbook", "next"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(entry,)):
                with patch("ordo.cli.activate_playbook", return_value=activated):
                    with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertNotIn("requires a workflow name", stderr.getvalue())

    def test_cli_next_text_output_is_compact_and_shows_scores(self) -> None:
        entry = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow_description="Inspect issue context",
            workflow_category="inspect",
            workflow_when=None,
            working_directory=None,
        )
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(entry,)):
                with patch("ordo.cli.activate_playbook", return_value=activated):
                    with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Next workflow: inspect-issue (1040, +0/-0, unrelated, ready)", output)
        self.assertIn("Status: ready now", output)
        self.assertNotIn('"best_candidate"', output)

    def test_cli_next_graph_text_output_shows_graph_sections(self) -> None:
        entry = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow_description="Inspect issue context",
            workflow_category="inspect",
            workflow_when=None,
            working_directory=None,
        )
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next", "--graph"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(entry,)):
                with patch("ordo.cli.activate_playbook", return_value=activated):
                    with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Graph:", output)
        self.assertIn("active state paths:", output)
        self.assertIn("workflows:", output)
        self.assertIn("scores:", output)
        self.assertIn("guard factors:", output)
        self.assertIn("state factors:", output)

    def test_cli_next_graph_json_includes_graph_payload(self) -> None:
        entry = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow_description="Inspect issue context",
            workflow_category="inspect",
            workflow_when=None,
            working_directory=None,
        )
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next", "--graph", "--json"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(entry,)):
                with patch("ordo.cli.activate_playbook", return_value=activated):
                    with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("graph", payload)
        self.assertIn("workflows", payload["graph"])
        self.assertIn("score_breakdown", payload["graph"]["workflows"][0])

    def test_cli_graph_flag_is_only_supported_with_next(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "--graph", "plan", "inspect-issue"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main()

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("--graph is only supported with next", stderr.getvalue())

    def test_cli_next_global_filters_input_overrides_per_candidate_workflow(self) -> None:
        list_entry_mobile = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="mobile-run-android-dev-usb",
            workflow_description="Run mobile dev build",
            workflow_category="mobile",
            workflow_when=None,
            working_directory=None,
        )
        list_entry_story = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="story-get-next-task-for-work",
            workflow_description="Choose next task",
            workflow_category="story",
            workflow_when=None,
            working_directory=None,
        )
        detailed_mobile = SimpleNamespace(**list_entry_mobile.__dict__, inputs=(WorkflowCatalogInput(name="device_id"),))
        detailed_story = SimpleNamespace(**list_entry_story.__dict__, inputs=(WorkflowCatalogInput(name="issue_number"),))
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow=object(),
            profile=None,
            working_directory=None,
            available_profiles=None,
            profile_working_directories=None,
            diagnostics=(),
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXPLAIN,
            status=RuntimeStatus.OK,
            diagnostics=(),
            plan=ExecutionPlan(),
            outputs={
                "can_execute": True,
                "allowed_state": "allowed",
                "analysis_complete": True,
                "explanation": {"allowed": True, "category": "ok", "blockers": []},
                "guard_coverage": [],
                "relevant_guard_count": 0,
                "evaluated_relevant_guard_count": 0,
            },
        )

        activate_calls: list[dict[str, object]] = []

        def activate_side_effect(*, workflow_name, profile_name, input_overrides, playbook_path):
            activate_calls.append({
                "workflow_name": workflow_name,
                "input_overrides": dict(input_overrides),
            })
            return SimpleNamespace(**activated.__dict__, workflow_name=workflow_name)

        def inspect_side_effect(workflow_name, *, playbook_path=None):
            if workflow_name == "mobile-run-android-dev-usb":
                return detailed_mobile
            return detailed_story

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next", "--input", "device_id=demo-device", "--json"]):
            with patch("ordo.cli.list_playbook_workflows", return_value=(list_entry_mobile, list_entry_story)):
                with patch("ordo.cli.inspect_playbook_workflow", side_effect=inspect_side_effect):
                    with patch("ordo.cli.activate_playbook", side_effect=activate_side_effect):
                        with patch("ordo.cli.explain_workflow", return_value=runtime_result):
                            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                                exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            activate_calls,
            [
                {"workflow_name": "mobile-run-android-dev-usb", "input_overrides": {"device_id": "demo-device"}},
                {"workflow_name": "story-get-next-task-for-work", "input_overrides": {}},
            ],
        )

    def test_cli_top_level_help_mentions_workflows_and_positional_execution(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "--help"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main()

        self.assertEqual(ctx.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("workflows  list workflow entries", help_text)
        self.assertIn("check    check whether the workflow can be run now", help_text)
        self.assertIn("run `ordo-help` for the detailed Ordo reference", help_text)

    def test_cli_workflows_help_mentions_list_and_show(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "workflows", "--help"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertIn("ordo-playbook workflows list", stdout.getvalue())

    def test_cli_mode_help_uses_positional_workflow_examples(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "plan", "--help"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        help_text = stdout.getvalue()
        self.assertIn("usage: ordo-playbook [options] plan WORKFLOW", help_text)
        self.assertIn("ordo-playbook plan set-active-task", help_text)

    def test_cli_next_help_mentions_no_argument_mode(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "next", "--help"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        help_text = stdout.getvalue()
        self.assertIn("usage: ordo-playbook [options] next", help_text)
        self.assertIn("ordo-playbook next", help_text)
        self.assertIn("ordo-playbook next --graph", help_text)

    def test_cli_run_help_mentions_progress_steps_flag(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "run", "--help"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        help_text = stdout.getvalue()
        self.assertIn("usage: ordo-playbook [options] run WORKFLOW", help_text)
        self.assertIn("ordo-playbook --progress-steps run set-active-task", help_text)

    def test_cli_workflows_list_returns_catalog_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      zeta-task:
                        file: zeta-task.yml
                        category: lifecycle
                        when: Use after finishing implementation work
                      inspect-issue:
                        file: inspect-issue.yml
                        description: Inspect one issue and prepare local context
                        category: inspect
                        when: Use when you need issue details without changing state
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
            (root / ".ordo" / "workflows" / "zeta-task.yml").write_text(
                "version: 0\nworkflow: zeta-task\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "workflows", "list"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "workflows.list")
            self.assertEqual([item["category"] for item in payload["categories"]], ["lifecycle", "inspect"])
            self.assertEqual([item["workflow"] for item in payload["categories"][0]["workflows"]], ["zeta-task"])
            self.assertEqual([item["workflow"] for item in payload["categories"][1]["workflows"]], ["inspect-issue"])
            self.assertEqual(payload["categories"][1]["workflows"][0]["description"], "Inspect one issue and prepare local context")
            self.assertEqual(payload["categories"][1]["workflows"][0]["when"], "Use when you need issue details without changing state")
            self.assertEqual(payload["categories"][0]["workflows"][0]["when"], "Use after finishing implementation work")

    def test_cli_workflows_show_omits_declared_inputs_in_plain_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        description: Inspect one issue and prepare local context
                        category: inspect
                        when: Use when you need issue details without changing state
                        working_directory: ../repo
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "repo").mkdir()
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: inspect-issue
                    inputs:
                      repository:
                        description: GitHub repository slug
                        hint: Use owner/name format
                      issue_number:
                        description: Numeric issue id
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
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "workflows.show")
            self.assertEqual(payload["workflow"], "inspect-issue")
            self.assertEqual(payload["description"], "Inspect one issue and prepare local context")
            self.assertEqual(payload["category"], "inspect")
            self.assertEqual(payload["when"], "Use when you need issue details without changing state")
            self.assertEqual(payload["working_directory"], "../repo")
            self.assertEqual(payload["inputs"], {})
            self.assertEqual(payload["caller_inputs"], [])
            self.assertNotIn("optional_caller_inputs", payload)
            self.assertNotIn("declared_inputs", payload)

    def test_cli_workflows_show_json_retains_declared_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
                        description: GitHub repository slug
                        hint: Use owner/name format
                      issue_number:
                        description: Numeric issue id
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
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["inputs"], {})
            self.assertEqual(payload["declared_inputs"][0], {"name": "repository", "description": "GitHub repository slug", "hint": "Use owner/name format"})
            self.assertEqual(payload["declared_inputs"][1], {"name": "issue_number", "description": "Numeric issue id"})

    def test_cli_workflows_show_separates_bound_and_caller_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: owner/repo
                          issue_number:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  issue_number: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["inputs"], {"repository": "owner/repo", "issue_number": None})
            self.assertEqual(payload["caller_inputs"], ["issue_number"])
            self.assertNotIn("declared_inputs", payload)

    def test_cli_workflows_show_reports_optional_caller_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                        with:
                          repository: owner/repo
                          issue_number:
                          close_comment?:
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository: {}\n  issue_number: {}\n  close_comment:\n    required: false\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["inputs"], {"repository": "owner/repo", "issue_number": None, "close_comment": None})
            self.assertEqual(payload["caller_inputs"], ["issue_number"])
            self.assertEqual(payload["optional_caller_inputs"], ["close_comment"])

    def test_cli_workflows_show_omits_empty_values_when_not_declared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  repository:\n    description: GitHub repository slug\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "inspect-issue"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertNotIn("description", payload)
            self.assertNotIn("category", payload)
            self.assertNotIn("when", payload)
            self.assertNotIn("working_directory", payload)
            self.assertEqual(payload["inputs"], {})
            self.assertNotIn("declared_inputs", payload)

    def test_cli_workflows_show_reports_unknown_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows: {}\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "workflows", "show", "missing", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "activation")
            self.assertEqual(payload["diagnostics"][0]["code"], "playbook.workflow.missing")

    def test_cli_runs_mode_inside_activated_working_directory(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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

        def fake_run_mode(_mode, _workflow, _profile, *_args, **_kwargs):
            observed["cwd"] = os.getcwd()
            return runtime_result

        with patch("sys.argv", ["ordo-playbook", "plan", "inspect-issue"]):
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
            with patch("sys.argv", ["ordo-playbook", "plan", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "activation")
            self.assertEqual(payload["status"], "resolution_error")
            self.assertEqual(payload["diagnostics"][0]["code"], "playbook.discovery.missing")
            self.assertEqual(payload["diagnostics"][0]["details"]["category"], "discovery")

    def test_cli_activation_error_surfaces_missing_input_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      story-get-task-for-work:
                        file: story-get-task-for-work.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "story-get-task-for-work.yml").write_text(
                "version: 0\nworkflow: story-get-task-for-work\ninputs:\n  issue_number: {}\n  profile: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "run", "story-get-task-for-work", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "activation")
            self.assertEqual(payload["workflow"], "story-get-task-for-work")
            self.assertEqual(payload["missing_inputs"], ["issue_number", "profile"])
            self.assertEqual(payload["declared_inputs"], ["issue_number", "profile"])
            self.assertEqual(payload["input_transport"], "--input NAME=VALUE")
            self.assertIn("--input issue_number=<value>", payload["example"])
            self.assertIn("run story-get-task-for-work", payload["example"])

    def test_cli_activation_error_plain_output_is_compact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      story-get-task-for-work:
                        file: story-get-task-for-work.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "story-get-task-for-work.yml").write_text(
                "version: 0\nworkflow: story-get-task-for-work\ninputs:\n  issue_number: {}\n  profile: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "run", "story-get-task-for-work"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["mode"], "activation")
            self.assertEqual(payload["workflow"], "story-get-task-for-work")
            self.assertEqual(payload["missing_inputs"], ["issue_number", "profile"])
            self.assertIn("Missing required workflow inputs", payload["message"])
            self.assertIn("run story-get-task-for-work", payload["example"])
            self.assertNotIn("diagnostics", payload)
            self.assertNotIn("declared_inputs", payload)
            self.assertEqual(stdout.getvalue(), "")

    def test_cli_activation_error_example_uses_requested_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    workflows:
                      story-get-task-for-work:
                        file: story-get-task-for-work.yml
                    profiles: {}
                    states: {}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "story-get-task-for-work.yml").write_text(
                "version: 0\nworkflow: story-get-task-for-work\ninputs:\n  issue_number: {}\n  profile: {}\nblocks:\n  - guards: []\n  - steps: []\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "check", "story-get-task-for-work", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertIn(" check story-get-task-for-work", payload["example"])
            self.assertNotIn(" run story-get-task-for-work", payload["example"])

    def test_cli_run_mode_executes_empty_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
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
            with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["results"], [{"summary": "Workflow completed with no explicit result or published output."}])

    def test_cli_run_mode_surfaces_published_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "ordo.yaml").write_text(
                "version: 1\nworkflows:\n  inspect-issue:\n    file: inspect-issue.yml\nprofiles: {}\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\nblocks:\n  - steps:\n      - name: publish\n        publish:\n          summary: \"done\"\n          changed: true\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload, {"status": "ok", "published": [{"summary": "done", "changed": True}]})

    def test_cli_run_mode_uses_compact_failure_payload(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.EXECUTION_ERROR,
            diagnostics=(
                Diagnostic(
                    code="action.gh_project_issue_priority_set.priority_not_found",
                    level="error",
                    message="GitHub project priority was not found",
                    path=(),
                    details={"priority": "high"},
                ),
            ),
            failed_step="Set task priority",
            outputs={"operation_results": [{"huge": True}], "block_items": [{"verbose": True}]},
        )

        with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "execution_error")
        self.assertEqual(payload["failed_step"], "Set task priority")
        self.assertEqual(payload["diagnostics"][0]["code"], "action.gh_project_issue_priority_set.priority_not_found")
        self.assertNotIn("operation_results", payload)
        self.assertNotIn("workflow", payload)

    def test_cli_run_includes_routine_failure_details(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.EXECUTION_ERROR,
            diagnostics=(),
            failed_step="Run routine",
            operation_results=(
                OperationResult(
                    status="routine_failed",
                    summary="Routine 'demo.fail' failed",
                    outputs={
                        "routine_id": "demo.fail",
                        "exit_code": 3,
                        "stdout_log_path": "/tmp/ordo/demo.stdout.log",
                        "stderr_log_path": "/tmp/ordo/demo.stderr.log",
                        "stdout_tail": "before fail",
                        "stderr_tail": "boom",
                    },
                ),
            ),
        )

        with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "execution_error")
        self.assertEqual(payload["failed_step"], "Run routine")
        self.assertEqual(payload["failure"]["kind"], "routine_failed")
        self.assertEqual(payload["failure"]["routine_id"], "demo.fail")
        self.assertEqual(payload["failure"]["exit_code"], 3)
        self.assertEqual(payload["failure"]["stdout_log_path"], "/tmp/ordo/demo.stdout.log")
        self.assertEqual(payload["failure"]["stderr_log_path"], "/tmp/ordo/demo.stderr.log")
        self.assertEqual(payload["failure"]["stdout_tail"], "before fail")
        self.assertEqual(payload["failure"]["stderr_tail"], "boom")

    def test_cli_run_includes_external_failure_payload_without_operation_results(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.EXECUTION_ERROR,
            diagnostics=(
                Diagnostic(
                    code="runtime.value.call_probe_failed",
                    level="error",
                    message="Read-only probe call 'gh.pr' failed due to external github failure reported by gh (authentication failure): GitHub pull request probe failed",
                    details={
                        "is_external": True,
                        "classification": "auth_failed",
                        "external_tool": "gh",
                        "external_system": "github",
                        "argv_summary": "gh api repos/owner/repo/pulls/7",
                        "stderr_excerpt": "authentication required",
                        "suggested_checks": ["Run 'gh auth status' to verify GitHub CLI authentication."],
                        "target": "gh.pr",
                        "reference": "gh.pr",
                    },
                ),
            ),
            failed_step="Build digest payload",
        )

        with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["failure"]["kind"], "external_failure")
        self.assertEqual(payload["failure"]["tool"], "gh")
        self.assertEqual(payload["failure"]["system"], "github")
        self.assertEqual(payload["failure"]["classification"], "auth_failed")
        self.assertEqual(payload["failure"]["argv_summary"], "gh api repos/owner/repo/pulls/7")
        self.assertEqual(payload["failure"]["stderr_excerpt"], "authentication required")
        self.assertEqual(payload["failure"]["target"], "gh.pr")
        self.assertEqual(payload["failure"]["reference"], "gh.pr")
        self.assertIn("external github failure reported by gh", payload["failure"]["summary"])
        self.assertIn("gh auth status", payload["failure"]["suggested_checks"][0])

    def test_cli_run_hides_raw_diagnostic_details_without_json(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="story-to-ready",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.EXECUTION_ERROR,
            diagnostics=(
                Diagnostic(
                    code="runtime.step.gate.failed",
                    level="error",
                    message="Item 'kergma-lw/checklist-mobile#1' failed gate 'Gate linked task readiness': step.linked_project_issue.outputs.status | eq(\"Ready\")",
                    details={
                        "fan_out_item": "kergma-lw/checklist-mobile#1",
                        "failed_conditions": ['step.linked_project_issue.outputs.status | eq("Ready")'],
                    },
                ),
            ),
            failed_step="Gate linked task readiness",
        )

        with patch("sys.argv", ["ordo-playbook", "run", "story-to-ready"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["failed_step"], "Gate linked task readiness")
        self.assertIn("failed gate", payload["message"])
        self.assertNotIn("diagnostics", payload)

    def test_cli_run_surfaces_guard_failure_message_without_diagnostics(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="story-to-ready",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.GUARD_FAILED,
            diagnostics=(),
            failed_guard="git.worktree.clean",
            outputs={
                "active_profile": "mobile",
                "current_working_directory": "/tmp/mobile",
                "guard_details": [
                    {
                        "reference": "git.worktree.clean",
                        "failed_subcondition": "git.worktree.clean",
                    }
                ]
            },
        )

        with patch("sys.argv", ["ordo-playbook", "run", "story-to-ready"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["failed_guard"], "git.worktree.clean")
        self.assertEqual(payload["message"], "Guard blocked execution for 'git.worktree.clean'")
        self.assertEqual(payload["active_profile"], "mobile")
        self.assertEqual(payload["working_directory"], "/tmp/mobile")
        self.assertNotIn("diagnostics", payload)

    def test_cli_run_includes_routine_start_failure_details(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
            workflow_name="inspect-issue",
            workflow=object(),
            profile=None,
            working_directory=None,
            diagnostics=(),
            available_profiles={},
            profile_working_directories={},
        )
        runtime_result = RuntimeResult(
            mode=Mode.EXECUTE,
            status=RuntimeStatus.EXECUTION_ERROR,
            diagnostics=(),
            failed_step="Run routine",
            operation_results=(
                OperationResult(
                    status="execution_error",
                    summary="Routine 'demo.fail' could not be started",
                    outputs={
                        "routine_id": "demo.fail",
                        "stdout_log_path": "/tmp/ordo/demo.stdout.log",
                        "stderr_log_path": "/tmp/ordo/demo.stderr.log",
                        "stdout_tail": "",
                        "stderr_tail": "",
                    },
                ),
            ),
        )

        with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
            with patch("ordo.cli.activate_playbook", return_value=activated):
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["failure"]["kind"], "routine_start_failed")
        self.assertEqual(payload["failure"]["routine_id"], "demo.fail")
        self.assertEqual(payload["failure"]["message"], "Routine 'demo.fail' could not be started")
        self.assertNotIn("exit_code", payload["failure"])

    def test_cli_run_emits_only_one_top_level_fallback_when_internal_layers_publish_no_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            (root / ".ordo" / "repo.json").write_text('{"active_profile": "backend"}\n', encoding="utf-8")
            (root / ".ordo" / "ordo.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    pre_run:
                      - file: workflows/switch-active-profile.yml
                        state_bindings:
                          shared_state: shared_state
                    defaults:
                      profile: backend
                    workflows:
                      inspect-issue:
                        file: inspect-issue.yml
                    profiles:
                      backend:
                        file: backend.yml
                    states:
                      shared_state:
                        path: repo.json
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "switch-active-profile.yml").write_text(
                "version: 0\nworkflow: switch-active-profile\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: switch\n        profile_switch: state.shared_state[inputs.active_profile_key]\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "nested.yml").write_text(
                "version: 0\nworkflow: nested\nblocks:\n  - steps:\n      - name: nested-value\n        value: \"ok\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "inspect-issue.yml").write_text(
                "version: 0\nworkflow: inspect-issue\ninputs:\n  active_profile_key: active_profile\nblocks:\n  - steps:\n      - name: nested\n        run: nested.yml\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text("name: backend\n", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch("sys.argv", ["ordo-playbook", "run", "inspect-issue", "--json"]):
                with patch("os.getcwd", return_value=str(root)):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload,
                {
                    "status": "ok",
                    "active_profile": "backend",
                    "results": [{"summary": "Workflow completed with no explicit result or published output."}],
                },
            )

    def test_cli_passes_input_overrides_to_playbook_activation(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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

        with patch("sys.argv", ["ordo-playbook", "--input", "enabled=true", "--input", "count=3", "plan", "inspect-issue"]):
            with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(activate_mock.call_args.kwargs["input_overrides"], {"enabled": True, "count": 3})

    def test_cli_keeps_yaml_like_inline_input_as_raw_text(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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

        with patch("sys.argv", ["ordo-playbook", "--input", "body=- item", "plan", "inspect-issue"]):
            with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(activate_mock.call_args.kwargs["input_overrides"], {"body": "- item"})

    def test_cli_coerces_simple_float_and_false_inline_inputs(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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

        with patch("sys.argv", ["ordo-playbook", "--input", "ratio=3.14", "--input", "enabled=false", "plan", "inspect-issue"]):
            with patch("ordo.cli.activate_playbook", return_value=activated) as activate_mock:
                with patch("ordo.cli._run_mode", return_value=runtime_result):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = cli_main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(activate_mock.call_args.kwargs["input_overrides"], {"ratio": 3.14, "enabled": False})

    def test_cli_passes_input_file_overrides_to_playbook_activation(self) -> None:
        activated = SimpleNamespace(
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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
                    "--input",
                    "enabled=true",
                    "--input-file",
                    f"body={body_path}",
                    "plan",
                    "inspect-issue",
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
            playbook_path=Path("/tmp/.ordo/ordo.yaml"),
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
                    "--input",
                    "body=inline",
                    "--input-file",
                    f"body={body_path}",
                    "plan",
                    "inspect-issue",
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

    def test_cli_rejects_legacy_workflow_flag(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.argv", ["ordo-playbook", "--workflow", "inspect-issue", "plan"]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main()

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("unrecognized arguments: --workflow", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
