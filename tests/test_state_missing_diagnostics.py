import json
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from ordo.model.diagnostic import Diagnostic, attribute_state_missing_diagnostics, group_state_missing_diagnostics
from ordo.model.runtime import Mode, OperationResult, RuntimeResult, RuntimeStatus
from ordo.runtime import check_workflow, execute_workflow, assess_workflow_readiness, load_workflow_file, load_workflow_text, plan_workflow, review_workflow
from ordo.runtime.local_expression_engine import core
from ordo.runtime.nexting import build_next_candidate
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value
from tests.support import STANDARD_CONNECTOR_PROVIDER


CODE = "runtime.value.state_missing"


def make_workflow(tmp_path, blocks, *, bindings='let:\n  saved: state.memory["key"].value\n'):
    workflow = load_workflow_text(
        "version: 0\nworkflow: missing-state\nstate_needs:\n  memory: {}\n  other: {}\n"
        + bindings + "blocks:\n" + blocks
    )
    return replace(workflow, state_bindings={"memory": "store", "other": "alias"},
                   states={"store": str(tmp_path / "private.json"), "alias": str(tmp_path / "private.json")})


def missing(result):
    return [diagnostic for diagnostic in result.diagnostics if diagnostic.code == CODE]


REPEATED = '''  - guards:
      - saved == 1
      - saved == 2
  - steps:
      - name: read
        value: saved
  - guards:
      - "true"
'''


@pytest.mark.parametrize("evaluate", [check_workflow, review_workflow, plan_workflow, assess_workflow_readiness, execute_workflow])
def test_repeated_let_guards_and_value_are_grouped_across_modes(tmp_path, evaluate):
    workflow = make_workflow(tmp_path, REPEATED)
    with patch.object(core, "read_state_document", wraps=core.read_state_document) as reads:
        result = evaluate(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    diagnostics = missing(result)
    assert len(diagnostics) == 1, result.diagnostics
    diagnostic = diagnostics[0]
    assert diagnostic.path == ()
    assert diagnostic.details["occurrence_count"] == 3
    assert "affected_sites" not in diagnostic.to_contract()["details"]
    assert reads.call_count == 3
    assert [site["path"] for site in diagnostic.details["reported_at"]] == [
        ["blocks", "0", "guards", "0"],
        ["blocks", "0", "guards", "1"],
        ["blocks", "1", "steps", "0"],
    ]
    assert diagnostic.details["key"] == "key"
    assert diagnostic.details["fields"] == ["value"]
    assert str(tmp_path / "private.json") not in json.dumps(diagnostic.to_contract())
    original = [d for operation in result.operation_results for d in operation.diagnostics if d.code == CODE]
    assert len(original) == 2
    assert all("occurrence_count" not in d.details for d in original)


def test_next_grouping_is_candidate_local(tmp_path):
    result = assess_workflow_readiness(make_workflow(tmp_path, REPEATED), connector_provider=STANDARD_CONNECTOR_PROVIDER)
    candidates = [build_next_candidate(
        workflow=name, description=None, workflow_category=None, when=None,
        working_directory=None, runtime_result=result,
    ) for name in ("first", "second")]
    assert [missing(candidate)[0].details["occurrence_count"] for candidate in candidates] == [3, 3]
    assert candidates[0].to_contract()["diagnostics"] == candidates[1].to_contract()["diagnostics"]


def test_aliases_preserve_per_site_expression_and_state(tmp_path):
    workflow = make_workflow(tmp_path, '''  - guards:
      - state.memory["key"].value == 1
      - state.other["key"].value == 2
''')
    diagnostic, = missing(check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER))
    sites = diagnostic.details["reported_at"]
    assert sites[0]["references"] == [{"expression": 'state.memory["key"].value', "state": "store"}]
    assert sites[1]["references"] == [{"expression": 'state.other["key"].value', "state": "alias"}]
    assert diagnostic.details["state"] == "store"


def test_count_tracks_emitted_errors_not_successful_presence_reads(tmp_path):
    workflow = make_workflow(tmp_path, '''  - guards:
      - is_missing(state.memory["key"].value)
      - state.memory["key"].value == 1
      - state.memory["key"].value == 2
''')
    with patch.object(core, "read_state_document", wraps=core.read_state_document) as reads:
        result = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    diagnostic, = missing(result)
    assert reads.call_count == 3
    assert diagnostic.details["occurrence_count"] == 2
    assert len(diagnostic.details["reported_at"]) == 2


def test_resolved_key_not_authored_key_expression_controls_identity(tmp_path):
    workflow = make_workflow(tmp_path, '''  - guards:
      - state.memory[1].value == 1
      - state.memory["1"].value == 2
''')
    diagnostic, = missing(check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER))
    assert diagnostic.details["key"] == "1"
    assert diagnostic.details["occurrence_count"] == 2
    assert len(diagnostic.details["reported_at"]) == 2


def test_storage_aliases_are_not_canonicalized_by_filesystem_identity(tmp_path):
    workflow = make_workflow(tmp_path, '''  - guards:
      - state.memory["key"].value == 1
      - state.other["key"].value == 2
''')
    workflow = replace(workflow, states={**workflow.states, "alias": str(tmp_path / "sub" / ".." / "private.json")})
    diagnostics = missing(check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER))
    assert len(diagnostics) == 2
    assert all("occurrence_count" not in diagnostic.details for diagnostic in diagnostics)


@pytest.mark.parametrize("second,storage", [
    ('state.memory["different"].value', "same"),
    ('state.memory["key"].other', "same"),
    ('state.memory["key"]', "same"),
    ('state.other["key"].value', "different"),
])
def test_different_targets_remain_singletons(tmp_path, second, storage):
    workflow = make_workflow(tmp_path, '  - guards:\n      - saved == 1\n      - ' + second + ' == 2\n')
    if storage == "different":
        workflow = replace(workflow, states={**workflow.states, "alias": str(tmp_path / "different.json")})
    diagnostics = missing(check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER))
    assert len(diagnostics) == 2
    assert all("occurrence_count" not in d.details and "reported_at" not in d.details for d in diagnostics)
    assert [d.path for d in diagnostics] == [("blocks", "0", "guards", str(index)) for index in range(2)]


def test_singleton_preserves_details_and_error_identity(tmp_path):
    workflow = make_workflow(tmp_path, "  - guards: []\n")
    with pytest.raises(ValueResolutionError) as error:
        resolve_runtime_value('${state.memory["key"].value}', workflow)
    diagnostic = error.value.to_diagnostic(path=("blocks", "0", "steps", "0"))
    assert diagnostic.details == {
        "expression": 'state.memory["key"].value', "state": "store", "key": "key", "fields": ["value"],
    }
    assert diagnostic._state_missing_target == (str(tmp_path / "private.json"), "key", ("value",))
    result = RuntimeResult(mode=Mode.EXECUTE, status=RuntimeStatus.EXECUTION_ERROR, diagnostics=(diagnostic,))
    assert result.diagnostics[0] is diagnostic
    assert "private.json" not in json.dumps(result.to_contract())
    assert "private.json" not in repr(diagnostic)


def test_cwd_identity_is_captured_at_evaluation_without_relookup(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    workflow = replace(make_workflow(tmp_path, "  - guards: []\n"), states={"store": "private.json", "alias": "private.json"})
    diagnostics = []
    for directory in (first, second, first):
        monkeypatch.chdir(directory)
        with pytest.raises(ValueResolutionError) as error:
            resolve_runtime_value('${state.memory["key"].value}', workflow)
        diagnostics.append(error.value.to_diagnostic())
    with patch.object(core, "resolve_state_target", side_effect=AssertionError("target reevaluated")), \
         patch.object(core, "read_state_document", side_effect=AssertionError("state reread")):
        grouped = group_state_missing_diagnostics(tuple(diagnostics))
    assert len(grouped) == 2
    assert grouped[0].details["occurrence_count"] == 2
    assert "occurrence_count" not in grouped[1].details


def test_nested_groups_compose_and_count_events_not_unique_sites(tmp_path):
    workflow = make_workflow(tmp_path, "  - guards: []\n")
    with pytest.raises(ValueResolutionError) as error:
        resolve_runtime_value('${state.memory["key"].value}', workflow)
    original = error.value.to_diagnostic(path=("blocks", "0", "guards", "0"))
    alias = replace(original, details={**original.details, "expression": 'state.other["key"].value', "state": "alias"})
    child = group_state_missing_diagnostics((original, alias))
    assert child[0].path == original.path
    assert len(child[0].details["reported_at"]) == 1
    assert len(child[0].details["reported_at"][0]["references"]) == 2
    first = attribute_state_missing_diagnostics(child, ("blocks", "1", "steps", "0", "for_each", "0"), prefix=True)
    second = attribute_state_missing_diagnostics(child, ("blocks", "1", "steps", "0", "for_each", "1"), prefix=True)
    parent = group_state_missing_diagnostics(first + second)
    assert parent[0].path == ()
    assert parent[0].details["occurrence_count"] == 4
    assert len(parent[0].details["reported_at"]) == 2
    assert group_state_missing_diagnostics(parent)[0].to_contract() == parent[0].to_contract()
    assert "occurrence_count" not in original.details


def test_other_codes_and_unidentified_missing_events_are_not_grouped():
    diagnostic = Diagnostic(code=CODE, level="error", message="missing", details={"key": "key"})
    other = replace(diagnostic, code="runtime.value.input_missing", _state_missing_target=("private", "key", ()))
    assert group_state_missing_diagnostics((diagnostic, diagnostic, other, other)) == (diagnostic, diagnostic, other, other)


def test_run_only_guard_failures_are_grouped_after_effect_barrier(tmp_path):
    workflow = make_workflow(tmp_path, '''  - steps:
      - name: barrier
        uses: shell.command
        with:
          command: "not executed by this test"
  - guards:
      - saved == 1
      - saved == 2
''')
    preflight = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert missing(preflight) == []
    executor = Mock(return_value=OperationResult(status="ok"))
    result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER, step_executor=executor)
    executor.assert_called_once()
    assert result.status is RuntimeStatus.GUARD_FAILED
    diagnostic, = missing(result)
    assert diagnostic.details["occurrence_count"] == 2
    assert [site["path"] for site in diagnostic.details["reported_at"]] == [
        ["blocks", "1", "guards", "0"], ["blocks", "1", "guards", "1"],
    ]
    assert len([d for operation in result.operation_results for d in operation.diagnostics if d.code == CODE]) == 2


def test_run_only_value_failure_has_structural_site(tmp_path):
    workflow = make_workflow(tmp_path, '''  - steps:
      - name: read
        value: saved
''')
    assert missing(check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)) == []
    result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    diagnostic, = missing(result)
    assert result.status is RuntimeStatus.EXECUTION_ERROR
    assert diagnostic.path == ("blocks", "0", "steps", "0")
    assert "occurrence_count" not in diagnostic.details


@pytest.mark.parametrize("runtime_only", [False, True])
@pytest.mark.parametrize("evaluate", [check_workflow, execute_workflow])
def test_nested_run_paths_include_call_and_iteration_index(tmp_path, evaluate, runtime_only):
    (tmp_path / "child.yml").write_text('''version: 0
workflow: child
args:
  item: string
state_needs:
  memory: {}
blocks:
  - guards:
      - state.memory["key"].value == 1
      - state.memory["key"].value == 2
''')
    parent = tmp_path / "parent.yml"
    parent.write_text('''version: 0
workflow: parent
state_needs:
  memory: {}
blocks:
  - steps:
      - name: call
        run: child.yml
        for_each: ${["sensitive item", "not visited"]}
''')
    workflow = replace(load_workflow_file(parent), state_bindings={"memory": "store"}, states={"store": str(tmp_path / "private.json")})
    if runtime_only:
        barrier = make_workflow(tmp_path, '''  - steps:
      - name: barrier
        uses: shell.command
        with:
          command: "not executed by this test"
''').blocks[0]
        workflow = replace(workflow, blocks=(barrier, *workflow.blocks))
    kwargs = {"connector_provider": STANDARD_CONNECTOR_PROVIDER}
    if evaluate is execute_workflow:
        kwargs["step_executor"] = Mock(return_value=OperationResult(status="ok"))
    result = evaluate(workflow, **kwargs)
    if runtime_only and evaluate is check_workflow:
        assert missing(result) == []
        return
    diagnostic, = missing(result)
    assert diagnostic.details["occurrence_count"] == 2
    assert [site["path"] for site in diagnostic.details["reported_at"]] == [
        ["blocks", "1" if runtime_only else "0", "steps", "0", "for_each", "0", "blocks", "0", "guards", str(index)]
        for index in range(2)
    ]
    assert "sensitive item" not in json.dumps(diagnostic.details["reported_at"])
    assert "private.json" not in json.dumps(diagnostic.to_contract())


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("fan_out", [False, True])
def test_missing_run_binding_preserves_identity_and_returns_error_without_profile_crash(tmp_path, nested, fan_out):
    (tmp_path / "leaf.yml").write_text('''version: 0
workflow: leaf
args:
  payload: string
  item:
    type: string
    default: null
blocks:
  - steps:
      - name: never-reached
        value: ${true}
''')
    binding_caller = tmp_path / "binding-caller.yml"
    binding_caller.write_text('''version: 0
workflow: binding-caller
args:
  item:
    type: string
    default: null
state_needs:
  memory: {}
blocks:
  - steps:
      - name: bind
        run: leaf.yml
        with:
          payload: ${state.memory["key"].value}
''' + ('        for_each: ${["inner private item", "unvisited inner item"]}\n' if fan_out else "")
        + '  - guards:\n      - "true"\n')
    source = binding_caller
    if nested:
        source = tmp_path / "parent.yml"
        source.write_text('''version: 0
workflow: parent
state_needs:
  memory: {}
blocks:
  - steps:
      - name: outer
        run: binding-caller.yml
''' + ('        for_each: ${["outer private item", "unvisited outer item"]}\n' if fan_out else ""))
    workflow = replace(load_workflow_file(source), state_bindings={"memory": "store"}, states={"store": str(tmp_path / "private.json")})

    # Unknown run bindings remain a check barrier, not emitted missing-state events.
    preflight = check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert preflight.status is RuntimeStatus.OK, preflight.diagnostics
    assert preflight.outputs["allowed_state"] == "unknown"
    assert missing(preflight) == []

    result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
    assert result.status is RuntimeStatus.EXECUTION_ERROR, result.diagnostics
    diagnostic, = missing(result)
    call_path = ("blocks", "0", "steps", "0") + (("for_each", "0") if fan_out else ())
    assert diagnostic.path == (call_path if nested else ()) + call_path + ("with",)
    assert diagnostic._state_missing_target == (str(tmp_path / "private.json"), "key", ("value",))
    assert diagnostic.details["binding"] == "payload"
    assert diagnostic.details["run_block_index"] == 0
    assert diagnostic.details["run_step_index"] == 0
    assert diagnostic.details["expression"] == 'state.memory["key"].value'
    assert diagnostic.details["state"] == "store"
    assert diagnostic.details["key"] == "key"
    assert diagnostic.details["fields"] == ["value"]
    assert "occurrence_count" not in diagnostic.details
    assert "reported_at" not in diagnostic.details
    assert "private.json" not in json.dumps(diagnostic.to_contract())
    if fan_out:
        assert diagnostic.details["fan_out_item"] == "inner private item"
        assert diagnostic.details["fan_out_item_index"] == 0
        assert diagnostic.details["fan_out_item_count"] == 2
    else:
        assert "fan_out_item" not in diagnostic.details

    # Grouping contextualized events must not newly disclose iteration values in sites.
    grouped, = group_state_missing_diagnostics((diagnostic, diagnostic))
    assert grouped.details["occurrence_count"] == 2
    assert len(grouped.details["reported_at"]) == 1
    assert "private item" not in json.dumps(grouped.details["reported_at"])
    assert "private.json" not in json.dumps(grouped.to_contract())
    if fan_out:
        assert grouped.details["fan_out_item"] == "inner private item"
