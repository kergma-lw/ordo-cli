import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.model.json import authored_string_style
from ordo.model.profile import Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import LoadError, load_profile_file, load_profile_text, load_workflow_document_file, load_workflow_file, load_workflow_text, load_yaml_document, validate_workflow_document


class LoadingTest(unittest.TestCase):
    def test_load_yaml_document_preserves_plain_and_quoted_string_styles(self) -> None:
        payload = load_yaml_document(
            textwrap.dedent(
                '''
                plain: inputs.repository
                single: 'Story created'
                double: "Backlog"
                nested:
                  - step.issue.outputs.id
                  - "Done"
                '''
            )
        )

        self.assertEqual(authored_string_style(payload["plain"]), "plain")
        self.assertEqual(authored_string_style(payload["single"]), "single")
        self.assertEqual(authored_string_style(payload["double"]), "double")

    def test_load_rejects_gate_and_register_on_same_step(self) -> None:
        with self.assertRaises(LoadError) as context:
            load_workflow_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: gate-check
                    blocks:
                      - steps:
                          - name: mutate
                            uses: gh.issue.comment
                            gate: inputs.enabled
                            register: nope
                    """
                )
            )

        self.assertEqual(context.exception.diagnostics[0].code, "load.step.gate_register_conflict")

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

    def test_loads_publish_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: publish
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          summary: done
                          changed: true
                """
            )
        )

        self.assertEqual(workflow.steps[0].publish, {"summary": "done", "changed": True})
        self.assertEqual(workflow.to_contract()["blocks"][0]["steps"][0]["publish"], {"summary": "done", "changed": True})

    def test_loads_workflow_values_with_preserved_authored_string_styles(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                '''
                version: 0
                workflow: publish
                blocks:
                  - steps:
                      - name: publish
                        publish:
                          summary: "done"
                          issue_ref: step.issue.outputs.id
                      - name: inspect
                        uses: gh.issue
                        with:
                          repository: inputs.repository
                          body: 'literal body'
                      - name: result
                        result:
                          profile: "meta"
                          current: state.memory[inputs.key].branch
                      - name: fan-out
                        run: fragment.yml
                        for_each: inputs.items
                '''
            )
        )

        publish = workflow.steps[0].publish
        operation = workflow.steps[1].operation
        result = workflow.steps[2].result
        self.assertEqual(authored_string_style(publish["summary"]), "double")
        self.assertEqual(authored_string_style(publish["issue_ref"]), "plain")
        self.assertIsNotNone(operation)
        self.assertEqual(authored_string_style(operation.with_["repository"]), "plain")
        self.assertEqual(authored_string_style(operation.with_["body"]), "single")
        self.assertEqual(authored_string_style(result["profile"]), "double")
        self.assertEqual(authored_string_style(result["current"]), "plain")
        self.assertEqual(authored_string_style(workflow.steps[3].for_each), "plain")

    def test_loads_result_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: publish
                blocks:
                  - steps:
                      - name: result
                        result:
                          summary: done
                          changed: true
                """
            )
        )

        self.assertEqual(workflow.steps[0].result, {"summary": "done", "changed": True})
        self.assertEqual(workflow.to_contract()["blocks"][0]["steps"][0]["result"], {"summary": "done", "changed": True})

    def test_loads_run_step_with_for_each_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  items:
                    hint: demo
                blocks:
                  - steps:
                      - name: inspect-one
                        run: fragment.yml
                        for_each: ${inputs.items}
                        register: inspected
                """
            )
        )

        self.assertEqual(workflow.steps[0].for_each, "${inputs.items}")
        self.assertEqual(workflow.to_contract()["blocks"][0]["steps"][0]["for_each"], "${inputs.items}")

    def test_loads_inline_fan_out_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: inspect
                inputs:
                  items:
                    hint: demo
                blocks:
                  - steps:
                      - name: inspect-many
                        for_each: ${inputs.items}
                        steps:
                          - name: inspect-one
                            uses: gh.issue
                            with:
                              issue_number: ${item}
                            register: issue
                        register: inspected
                """
            )
        )

        self.assertEqual(workflow.steps[0].for_each, "${inputs.items}")
        self.assertIsNone(workflow.steps[0].run)
        self.assertIsNotNone(workflow.steps[0].steps)
        self.assertEqual(workflow.steps[0].steps[0].operation.uses, "gh.issue")
        self.assertEqual(workflow.to_contract()["blocks"][0]["steps"][0]["steps"][0]["with"]["issue_number"], "${item}")

    def test_loads_bare_step_if_field_into_typed_model(self) -> None:
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
                        if: inputs.enabled
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(workflow.steps[0].if_, "inputs.enabled")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["if"], "inputs.enabled")

    def test_loads_structured_list_step_if_field_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  enabled: true
                  ready: true
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if:
                          - inputs.enabled
                          - inputs.ready
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(workflow.steps[0].if_, ["inputs.enabled", "inputs.ready"])
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["if"], ["inputs.enabled", "inputs.ready"])

    def test_loads_structured_object_step_if_field_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  enabled: true
                  ready: true
                blocks:
                  - guards: []
                  - steps:
                      - name: inspect
                        if:
                          all:
                            - inputs.enabled
                            - any:
                                - inputs.ready
                                - not: inputs.enabled | not
                        uses: gh.issue
                """
            )
        )

        self.assertEqual(
            workflow.to_contract()["blocks"][1]["steps"][0]["if"],
            {"all": ["inputs.enabled", {"any": ["inputs.ready", {"not": "inputs.enabled | not"}]}]},
        )

    def test_loads_declared_workflow_inputs_without_runtime_values(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  repository:
                    description: GitHub repository
                  issue_number:
                    description: Numeric issue id
                blocks:
                  - guards: []
                  - steps: []
                """
            )
        )

        self.assertEqual(workflow.inputs, {})
        self.assertEqual(workflow.declared_inputs["repository"], {"description": "GitHub repository"})
        self.assertEqual(workflow.to_contract()["inputs"]["issue_number"], {"description": "Numeric issue id"})

    def test_loads_top_level_let_bindings_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                let:
                  issue: gh.issue(repository=inputs.repository, issue_number=inputs.issue_number)
                  issue_open: issue.state == "OPEN"
                blocks:
                  - guards: []
                  - steps: []
                """
            )
        )

        self.assertEqual(
            workflow.let_bindings,
            {
                "issue": "gh.issue(repository=inputs.repository, issue_number=inputs.issue_number)",
                "issue_open": 'issue.state == "OPEN"',
            },
        )
        self.assertEqual(workflow.to_contract()["let"]["issue_open"], 'issue.state == "OPEN"')

    def test_load_rejects_reserved_let_binding_name(self) -> None:
        with self.assertRaises(LoadError) as context:
            load_workflow_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: open-task
                    let:
                      inputs: inputs.repository
                    blocks:
                      - guards: []
                    """
                )
            )

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.let.reserved_name")

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

    def test_loads_run_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                blocks:
                  - guards: []
                  - steps:
                      - name: comment-and-status
                        run: github/comment-and-set-status
                        if: ${step.issue.outputs.open}
                        with:
                          comment: hello
                """
            )
        )

        self.assertEqual(workflow.steps[0].run, "github/comment-and-set-status")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["run"], "github/comment-and-set-status")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["if"], "${step.issue.outputs.open}")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["with"], {"comment": "hello"})

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

    def test_loads_profile_switch_step_into_typed_model(self) -> None:
        workflow = load_workflow_text(
            textwrap.dedent(
                """
                version: 0
                workflow: open-task
                inputs:
                  profile: {}
                blocks:
                  - guards: []
                  - steps:
                      - name: switch-profile
                        profile_switch: ${inputs.profile}
                """
            )
        )

        self.assertEqual(workflow.steps[0].profile_switch, "${inputs.profile}")
        self.assertEqual(workflow.to_contract()["blocks"][1]["steps"][0]["profile_switch"], "${inputs.profile}")

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

    def test_loads_profile_working_directory_into_typed_model(self) -> None:
        profile = load_profile_text(
            textwrap.dedent(
                """
                name: frontend
                inputs:
                  repo_dir: ../frontend
                working_directory: ${inputs.repo_dir}
                """
            )
        )

        self.assertEqual(profile.working_directory, "${inputs.repo_dir}")
        self.assertEqual(profile.to_contract()["working_directory"], "${inputs.repo_dir}")

    def test_loads_profile_connector_contexts_into_typed_model(self) -> None:
        profile = load_profile_text(
            textwrap.dedent(
                """
                name: backend-default
                connectors:
                  git:
                    directory: /repos/backend
                """
            )
        )

        self.assertEqual(profile.connectors["git"]["directory"], "/repos/backend")
        self.assertEqual(profile.to_contract()["connectors"]["git"]["directory"], "/repos/backend")

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

    def test_load_workflow_file_binds_fragment_args_and_flattens_fragment_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    inputs:
                      repository: {}
                      issue_number: {}
                    blocks:
                      - include: fragments/check-issue
                        with:
                          repository: ${inputs.repository}
                          issue_number: 7
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    description: Check issue fragment
                    args:
                      repository: string
                      issue_number: integer

                    blocks:
                      - steps:
                          - name: inspect
                            uses: gh.issue
                            with:
                              repository: ${args.repository}
                              issue_number: ${args.issue_number}
                            register: issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(len(workflow.blocks), 1)
        self.assertEqual(workflow.steps[0].operation.with_["repository"], "${inputs.repository}")
        self.assertEqual(workflow.steps[0].operation.with_["issue_number"], 7)
        self.assertEqual(workflow.steps[0].register, "issue")

    def test_load_workflow_file_allows_include_with_to_capture_caller_step_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - steps:
                          - name: outer
                            uses: gh.issue
                            register: outer_issue
                      - include: fragments/comment
                        with:
                          issue_id: ${step.outer_issue.outputs.id}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "comment.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      issue_id: string
                    steps:
                      - name: comment
                        uses: gh.issue.comment
                        with:
                          issue_id: ${args.issue_id}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertTrue(report.ok)
        self.assertEqual(payload["blocks"][1]["steps"][0]["with"]["issue_id"], "${step.outer_issue.outputs.id}")

    def test_load_workflow_file_rejects_missing_fragment_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text("args:\n  repository: string\nsteps: []\n", encoding="utf-8")

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.args.missing")

    def test_validate_workflow_document_rejects_undeclared_root_input_from_included_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: fragments/set-size
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "set-size.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: size
                        value: ${inputs.size}
                        register: size
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertEqual(report.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.inputs.undeclared_reference")
        self.assertEqual(report.diagnostics[0].path, ("blocks", "0", "steps", "0", "value"))

    def test_validate_workflow_document_accepts_declared_root_input_used_only_in_included_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    inputs:
                      size:
                        description: task size
                    blocks:
                      - include: fragments/set-size
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "set-size.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: size
                        value: ${inputs.size}
                        register: size
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertTrue(report.ok)

    def test_load_workflow_file_rejects_unknown_fragment_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n    with:\n      repository: repo/name\n      extra: true\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text("args:\n  repository: string\nsteps: []\n", encoding="utf-8")

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.args.unknown")

    def test_load_workflow_file_rejects_invalid_fragment_args_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text("args: nope\nsteps: []\n", encoding="utf-8")

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.args.invalid_declaration")

    def test_load_workflow_file_materializes_fragment_default_values_including_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: fragments/check-issue
                        with:
                          repository: repo/name
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      repository: string
                      project_id:
                        type: string
                        default: null
                      dry_run:
                        type: boolean
                        default: false
                    steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          repository: ${args.repository}
                          project_id: ${args.project_id}
                          dry_run: ${args.dry_run}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(workflow.steps[0].operation.with_["repository"], "repo/name")
        self.assertIsNone(workflow.steps[0].operation.with_["project_id"])
        self.assertFalse(workflow.steps[0].operation.with_["dry_run"])

    def test_load_workflow_file_accepts_explicit_null_binding_for_null_default_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - include: fragments/check-issue
                        with:
                          repository: repo/name
                          project_id: null
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      repository: string
                      project_id:
                        type: string
                        default: null
                    steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          repository: ${args.repository}
                          project_id: ${args.project_id}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(workflow.steps[0].operation.with_["repository"], "repo/name")
        self.assertIsNone(workflow.steps[0].operation.with_["project_id"])

    def test_load_workflow_file_allows_optional_fragment_arg_without_default_when_omitted_and_unused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      project_id:
                        type: string
                        required: false
                    steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            workflow = load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(workflow.to_contract()["blocks"], [{"steps": []}])

    def test_load_workflow_file_rejects_invalid_fragment_default_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      project_id:
                        type: string
                        default: false
                    steps: []
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.args.invalid_declaration")

    def test_load_workflow_file_allows_fragment_reference_to_caller_step_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - steps:
                          - name: outer
                            uses: gh.issue
                            register: outer_issue
                      - include: fragments/check-issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                "steps:\n  - name: comment\n    uses: gh.issue.comment\n    with:\n      issue_id: ${step.outer_issue.outputs.id}\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertTrue(report.ok)
        self.assertEqual(payload["blocks"][1]["steps"][0]["with"]["issue_id"], "${step.outer_issue.outputs.id}")

    def test_validation_allows_caller_reference_to_fragment_local_register(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    inputs:
                      repository: {}
                      issue_number: {}
                    blocks:
                      - include: fragments/check-issue
                        with:
                          repository: ${inputs.repository}
                          issue_number: ${inputs.issue_number}
                      - steps:
                          - name: comment
                            uses: gh.issue.comment
                            with:
                              issue_id: ${step.issue.outputs.id}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    args:
                      repository: string
                      issue_number: integer
                    steps:
                      - name: inspect
                        uses: gh.issue
                        with:
                          repository: ${args.repository}
                          issue_number: ${args.issue_number}
                        register: issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertTrue(report.ok)

    def test_validation_rejects_duplicate_register_name_across_include_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workflow_path = root / "workflow.yaml"
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path.write_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - steps:
                          - name: inspect-outer
                            uses: gh.issue
                            register: issue
                      - include: fragments/check-issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: inspect-inner
                        uses: gh.issue
                        register: issue
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            payload = load_workflow_document_file(workflow_path, launch_dir=root)
            report = validate_workflow_document(payload, source=str(workflow_path))

        self.assertFalse(report.ok)
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.step.duplicate_register")

    def test_load_workflow_file_rejects_fragment_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: remember
                        state_set:
                          state.task_memory[inputs.issue_ref].branch: demo
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.state_forbidden")

    def test_load_workflow_file_rejects_fragment_state_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fragments_dir = root / "fragments"
            fragments_dir.mkdir()
            workflow_path = root / "workflow.yaml"
            workflow_path.write_text(
                "version: 0\nworkflow: demo\nblocks:\n  - include: fragments/check-issue\n",
                encoding="utf-8",
            )
            (fragments_dir / "check-issue.yaml").write_text(
                textwrap.dedent(
                    """
                    steps:
                      - name: inspect
                        value: ${state.task_memory[inputs.issue_ref].branch}
                        register: branch
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(LoadError) as context:
                load_workflow_file(workflow_path, launch_dir=root)

        self.assertEqual(context.exception.diagnostics[0].code, "load.workflow.include.state_forbidden")


if __name__ == "__main__":
    unittest.main()
