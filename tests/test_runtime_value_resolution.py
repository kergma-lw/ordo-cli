import json
import tempfile
import unittest

from ordo.model.diagnostic import Diagnostic
from ordo.model.runtime import OperationResult
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import json_adapter as runtime_json_adapter
from ordo.runtime import execute_workflow, load_workflow_text
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value
from ordo.runtime.local_expression_engine.core import (
    ConditionObservationRequest,
    ConditionObservationResult,
    ReadOnlyObservationSession,
)
from ordo.runtime.representation_adapters import (
    RepresentationAdapterInvocation,
    adapter_read_result,
    adapter_write_result,
    register_representation_adapter,
    unregister_representation_adapter,
)

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeValueResolutionTest(unittest.TestCase):
    def tearDown(self) -> None:
        unregister_representation_adapter("fixture")
        unregister_representation_adapter("json")
        runtime_json_adapter._register()

    def test_execute_resolves_state_reference_in_step_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "owner/repo#1": {"command": "printf resolved-from-state"},
                    },
                    handle,
                )

            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${{state.task_memory[inputs.issue_ref].command}}
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.operation_results[0].status, "ok")
            self.assertEqual(result.operation_results[0].outputs.get("stdout"), "resolved-from-state")

    def test_execute_reports_missing_state_value_as_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = f"{temp_dir}/task-state.json"
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({}, handle)

            workflow = load_workflow_text(
                f"""
version: 0
workflow: open-task
inputs:
  issue_ref: owner/repo#1
state_needs:
  task_memory: {{}}
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${{state.task_memory[inputs.issue_ref].command}}
"""
            )
            workflow = Workflow(
                version=workflow.version,
                workflow=workflow.workflow,
                inputs=workflow.inputs,
                state_needs=workflow.state_needs,
                state_bindings={"task_memory": "repo_task_state"},
                states={"repo_task_state": state_path},
                guards=workflow.guards,
                steps=workflow.steps,
            )

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

            self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
            self.assertEqual(result.operation_results[0].status, "input_error")
            self.assertEqual(result.operation_results[0].diagnostics[0].code, "runtime.value.state_missing")

    def test_execute_resolves_format_expression_in_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: ${format("printf {}", format("{}/{}-{}", inputs.type | lower, inputs.issue_number, inputs.title | slug))}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "task/7-hello-world")

    def test_execute_resolves_bare_expression_in_step_input(self) -> None:
        workflow = load_workflow_text(
            '''
version: 0
workflow: open-task
inputs:
  command: "printf bare-input"
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command: inputs.command
'''
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "bare-input")

    def test_execute_resolves_yaml_format_object_in_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
blocks:
  - guards: []
  - steps:
      - name: run-command
        uses: shell.command
        with:
          command:
            format: "printf {}"
            args:
              -
                format: "{}/{}-{}"
                args:
                  - ${inputs.type | lower}
                  - ${inputs.issue_number}
                  - ${inputs.title | slug}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].status, "ok")
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "task/7-hello-world")

    def test_resolve_runtime_value_supports_workflow_let_binding(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: feat
  issue_number: 7
let:
  branch: format("{}/{}", inputs.type, inputs.issue_number)
blocks:
  - guards: []
  - steps: []
"""
        )

        value = resolve_runtime_value("${branch}", workflow)

        self.assertEqual(value, "feat/7")

    def test_resolve_runtime_value_supports_bare_authored_strings_in_expression_first_surfaces(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: bare-values
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps:
      - name: publish
        publish:
          repo: inputs.repository
          number: inputs.issue_number
          summary: "inputs.repository"
          nested:
            issue_ref:
              format: "{}#{}"
              args:
                - inputs.repository
                - inputs.issue_number
            label: "done"
"""
        )

        value = resolve_runtime_value(workflow.steps[0].publish, workflow)

        self.assertEqual(
            value,
            {
                "repo": "owner/repo",
                "number": 7,
                "summary": "inputs.repository",
                "nested": {"issue_ref": "owner/repo#7", "label": "done"},
            },
        )

    def test_execute_workflow_composes_json_cleanup_pipeline_across_steps(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: json-compose
blocks:
  - steps:
      - name: build
        value:
          title: "Demo"
          head_sha: "abc123"
          commit_id: 17
        register: digest
      - name: serialize
        value: '${json->set(value) with{root: "{}", value: step.digest.outputs.value}}'
        register: digest_json
      - name: clean
        value: step.digest_json.outputs.value
          | json..["head_sha"]->remove()
          | json..["commit_id"]->remove()
        register: digest_json_clean
      - name: publish
        publish:
          digest: step.digest_json_clean.outputs.value | json
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(list(result.published), [{"digest": {"title": "Demo"}}])
        self.assertEqual(workflow.step_results["digest_json_clean"]["outputs"]["value"], '{"title":"Demo"}')

    def test_resolve_runtime_value_supports_bare_for_each_values(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: fanout
inputs:
  items:
    - alpha
    - beta
blocks:
  - guards: []
  - steps:
      - name: inspect
        run: fragment.yml
        for_each: inputs.items
"""
        )

        value = resolve_runtime_value(workflow.steps[0].for_each, workflow)

        self.assertEqual(value, ["alpha", "beta"])

    def test_execute_resolves_registered_step_output_in_later_step_input(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - guards: []
  - steps:
      - name: inspect
        uses: shell.command
        register: first
        with:
          command: "printf hello"
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.first.outputs.stdout)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "hello")
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "hello")

    def test_execute_materializes_value_step_output_for_later_step(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
inputs:
  type: Task
  issue_number: 7
  title: Hello World
blocks:
  - guards: []
  - steps:
      - name: compute-branch
        value:
          format: "{}/{}-{}"
          args:
            - ${inputs.type | lower}
            - ${inputs.issue_number}
            - ${inputs.title | slug}
        register: branch
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.branch.outputs.value)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("value"), "task/7-hello-world")

    def test_resolve_runtime_value_dispatches_adapter_with_resolved_outer_bindings(self) -> None:
        seen: list[RepresentationAdapterInvocation] = []

        def handle(invocation: RepresentationAdapterInvocation):
            seen.append(invocation)
            return adapter_read_result({
                "family": invocation.family,
                "body": invocation.body,
                "root": invocation.root_value,
                "parameters": dict(invocation.parameters),
            })

        register_representation_adapter("fixture", handle)
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello", "name": "Tasks"})

        value = resolve_runtime_value(
            '${fixture["body"] with{root: inputs.body, section: inputs.name}}',
            workflow,
        )

        self.assertEqual(
            value,
            {
                "family": "fixture",
                "body": '["body"]',
                "root": "hello",
                "parameters": {"section": "Tasks"},
            },
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].root_value, "hello")
        self.assertEqual(seen[0].parameters, {"section": "Tasks"})

    def test_resolve_runtime_value_reports_host_binding_failure_before_adapter_dispatch(self) -> None:
        called = False

        def handle(_invocation: RepresentationAdapterInvocation):
            nonlocal called
            called = True
            return adapter_read_result("unexpected")

        register_representation_adapter("fixture", handle)
        workflow = Workflow(version=0, workflow="demo")

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${fixture["body"] with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.input_missing")
        self.assertFalse(called)

    def test_resolve_runtime_value_requires_outer_root_binding_for_adapter_dispatch(self) -> None:
        register_representation_adapter("fixture", lambda invocation: adapter_read_result(invocation.root_value))
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${fixture["body"] with{section: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_root_missing")

    def test_resolve_runtime_value_supports_cross_adapter_value_flow(self) -> None:
        register_representation_adapter("fixture", lambda invocation: adapter_read_result({"wrapped": invocation.root_value}))
        register_representation_adapter("json", lambda invocation: adapter_read_result(invocation.root_value[invocation.parameters["field"]]))
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello", "field": "wrapped"})

        value = resolve_runtime_value(
            '${json["field"] with{root: fixture["body"] with{root: inputs.body}, field: inputs.field}}',
            workflow,
        )

        self.assertEqual(value, "hello")

    def test_resolve_runtime_value_returns_updated_root_from_write_result(self) -> None:
        register_representation_adapter(
            "fixture",
            lambda invocation: adapter_write_result(f"{invocation.root_value}:{invocation.parameters['suffix']}"),
        )
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello", "suffix": "done"})

        value = resolve_runtime_value(
            '${fixture["body"]->set(suffix) with{root: inputs.body, suffix: inputs.suffix}}',
            workflow,
        )

        self.assertEqual(value, "hello:done")

    def test_resolve_runtime_value_supports_adapter_invocation_with_empty_body(self) -> None:
        seen: list[RepresentationAdapterInvocation] = []

        def handle(invocation: RepresentationAdapterInvocation):
            seen.append(invocation)
            return adapter_read_result(invocation.root_value)

        register_representation_adapter("fixture_empty", handle)
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello"})

        value = resolve_runtime_value('${fixture_empty with{root: inputs.body}}', workflow)

        self.assertEqual(value, "hello")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].body, "")

    def test_execute_resolves_registered_step_output_in_later_step_block(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: open-task
blocks:
  - guards: []
  - steps:
      - name: inspect
        uses: shell.command
        register: first
        with:
          command: "printf hello"
  - guards: []
  - steps:
      - name: replay
        uses: shell.command
        with:
          command: ${format("printf {}", step.first.outputs.stdout)}
"""
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.operation_results[0].outputs.get("stdout"), "hello")
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "hello")

    def test_resolve_runtime_value_reads_registered_step_outputs(self) -> None:
        workflow = load_workflow_text("version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps: []\n")

        value = resolve_runtime_value(
            "${step.issue.outputs.id}",
            workflow,
            step_results={"issue": OperationResult(status="ok", summary="inspected", outputs={"id": 17})},
        )

        self.assertEqual(value, 17)

    def test_resolve_runtime_value_reports_missing_registered_step(self) -> None:
        workflow = load_workflow_text("version: 0\nworkflow: demo\nblocks:\n  - guards: []\n  - steps: []\n")

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value("${step.issue.outputs.id}", workflow)

        self.assertEqual(context.exception.code, "runtime.value.step_missing")

    def test_resolve_runtime_value_supports_boolean_composition_when_enabled(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  enabled: true
  status: ok
blocks:
  - guards: []
  - steps: []
"""
        )

        value = resolve_runtime_value(
            '${inputs.enabled and (inputs.status | eq("ok"))}',
            workflow,
            allow_boolean_composition=True,
        )

        self.assertIs(value, True)

    def test_resolve_runtime_value_executes_read_only_calls_with_shared_session(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        observed: list[ConditionObservationRequest] = []
        session = ReadOnlyObservationSession(
            lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value="Issue body", reference="gh.issue")
        )

        value = resolve_runtime_value(
            "${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}",
            workflow,
            observation_session=session,
        )

        self.assertEqual(value, "Issue body")
        self.assertEqual(observed[0].fields, ("body",))

    def test_resolve_runtime_value_reuses_shared_session_in_nested_structures(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(status="ok", value="Issue body", reference="gh.issue")

        session = ReadOnlyObservationSession(observe)

        value = resolve_runtime_value(
            {
                "title": "${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}",
                "items": ["${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}"],
            },
            workflow,
            observation_session=session,
        )

        self.assertEqual(value, {"title": "Issue body", "items": ["Issue body"]})
        self.assertEqual(count, 1)

    def test_resolve_runtime_value_reuses_session_for_ast_equivalent_call_formatting(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        count = 0

        def observe(_: ConditionObservationRequest) -> ConditionObservationResult:
            nonlocal count
            count += 1
            return ConditionObservationResult(status="ok", value="Issue body", reference="gh.issue")

        session = ReadOnlyObservationSession(observe)

        value = resolve_runtime_value(
            [
                "${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}",
                "${gh.issue( issue_number = inputs.issue_number , repository = inputs.repository ).body}",
            ],
            workflow,
            observation_session=session,
        )

        self.assertEqual(value, ["Issue body", "Issue body"])
        self.assertEqual(count, 1)

    def test_resolve_runtime_value_reports_probe_failure(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  repository: owner/repo
  issue_number: 7
blocks:
  - guards: []
  - steps: []
"""
        )
        session = ReadOnlyObservationSession(
            lambda _: ConditionObservationResult(
                status="probe_failed",
                value=None,
                diagnostics=(Diagnostic(code="probe.failed", level="error", message="boom", path=()),),
                reference="gh.issue",
            )
        )

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value(
                "${gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).body}",
                workflow,
                observation_session=session,
            )

        self.assertEqual(context.exception.code, "runtime.value.call_probe_failed")

    def test_resolve_runtime_value_can_feed_fs_file_content_into_key_value_adapter(self) -> None:
        workflow = load_workflow_text(
            """
version: 0
workflow: demo
inputs:
  path: /tmp/config.txt
blocks:
  - guards: []
  - steps: []
"""
        )
        observed: list[ConditionObservationRequest] = []
        session = ReadOnlyObservationSession(
            lambda request: observed.append(request)
            or ConditionObservationResult(status="ok", value='alpha: one\nbeta: "two"', reference="fs.file")
        )

        value = resolve_runtime_value(
            '${key_value with{root: fs.file(path=inputs.path).content, separator: ":"}}',
            workflow,
            observation_session=session,
        )

        self.assertEqual(value, {"alpha": "one", "beta": "two"})
        self.assertEqual(observed[0].target, ("fs", "file"))
        self.assertEqual(observed[0].fields, ("content",))


if __name__ == "__main__":
    unittest.main()
