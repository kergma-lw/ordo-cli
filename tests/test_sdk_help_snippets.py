"""Published Python is executed by actual family adapters without external IO."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from ordo.model.help_snippets import describe_help_snippets
from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.runtime.help_snippet_runner import verify_help_snippet


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SDK snippet attempted external execution")

    for path in ("subprocess.run", "subprocess.Popen", "socket.create_connection",
                 "ordo.connectors.operations.evaluate_probe", "ordo.connectors.operations.execute_operation",
                 "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(path, forbidden)


def example():
    return describe_help_snippets()["connector.authoring"]["canonical_examples"][0]


def world():
    return deepcopy(describe_help_snippet_worlds()["gh-sdk-probe-call"])


def run(**kwargs):
    return verify_help_snippet(**{
        "snippet": example()["python"], "world": "gh-sdk-probe-call",
        "insertion_mode": "sdk_probe_fragment", "target": "connector.authoring", **kwargs,
    })


def test_exact_published_python_runs_real_sdk_adapters():
    from connectors import _family
    from ordo.plugin_sdk import OperationContext

    original_call = OperationContext.call
    contexts = []

    def call(ctx, name, *, inputs=None):
        contexts.append((type(ctx), name, deepcopy(inputs)))
        return original_call(ctx, name, inputs=inputs)

    with (patch.object(_family, "_adapt_published_handler", wraps=_family._adapt_published_handler) as adapt,
          patch.object(OperationContext, "call", call)):
        result = run()
    assert adapt.call_count == 2
    assert contexts == [(OperationContext, "gh.pr.list", world()["inputs"]["filters"])]
    assert result.status == "ok"
    assert result.verification_path == "sdk_fixture_execution"
    assert result.python_text == example()["python"]
    assert result.workflow_text == ""
    assert result.runtime_result is None  # This is a connector handler, not workflow execution.
    assert result.operation_result.outputs == world()["probes"]["gh.pr.list"][0]["outputs"]
    assert [call["reference"] for call in result.calls] == ["gh.bootstrap", "gh.bootstrap", "gh.pr.list"]
    assert result.calls[-1]["inputs"] == world()["inputs"]["filters"]
    assert result.operation_result.raw["bootstrap"]["status"] == "ok"


@pytest.mark.parametrize("literal", ("${inputs.head}", "inputs.head", "{{ inputs.head }}", "state.repo[key]"))
def test_expression_looking_dependency_values_stay_literal(literal):
    fixture = world()
    fixture["inputs"]["filters"]["head"] = literal
    fixture["probes"]["gh.pr.list"][0]["with_"]["head"] = literal
    fixture["probes"]["gh.pr.list"][0]["outputs"]["head"] = literal
    before = deepcopy(fixture)
    result = run(overrides=fixture)
    assert result.status == "ok"
    assert result.calls[-1]["inputs"]["head"] == literal
    assert result.operation_result.outputs["head"] == literal
    assert fixture == before


def test_missing_dependency_input_is_real_sdk_failure_without_inheritance():
    fixture = world()
    del fixture["inputs"]["filters"]["state"]
    # Replace rather than deep-merge to genuinely omit the key. The host has
    # conflicting workflow and gh.pr.list guard bindings that must not fill it.
    with patch("ordo.runtime.help_snippet_runner.describe_help_snippet_worlds", return_value={"gh-sdk-probe-call": fixture}):
        result = run()
    assert result.status == "input_error"
    diagnostic, = result.operation_result.diagnostics
    assert diagnostic.code == "operation.input_missing"
    assert diagnostic.details == {"reference": "gh.pr.list", "input": "state"}
    assert [call["reference"] for call in result.calls] == ["gh.bootstrap", "gh.bootstrap"]


def test_dependency_failure_outcome_propagates_without_retry():
    fixture = world()
    fixture["probes"]["gh.pr.list"][0]["status"] = "probe_failed"
    result = run(overrides=fixture)
    assert result.status == "probe_failed"
    assert sum(call["reference"] == "gh.pr.list" for call in result.calls) == 1


@pytest.mark.parametrize("kwargs", (
    {"snippet": "def run(ctx):\n    return ctx.command(['gh'])\n"},
    {"snippet": "# changed\ndef run(ctx):\n    return ctx.call('gh.pr.list', inputs=ctx.input('filters'))\n"},
    {"world": "default"}, {"target": "connector.gh.pr.create"}, {"insertion_mode": "workflow_fragment"},
))
def test_noncanonical_source_and_placement_rejected_before_compilation(kwargs):
    with patch("builtins.compile", side_effect=AssertionError("Unadmitted Python compiled")):
        with pytest.raises(ValueError, match="exact published Python"):
            run(**kwargs)


@pytest.mark.parametrize("overrides", (
    {"implementation_text": "raise Exception()"}, {"inputs": {"code": "raise Exception()"}},
    {"inputs": {"filters": []}}, {"inputs": {"filters": {"unknown": "x"}}},
    {"actions": {"gh.pr.create": {}}}, {"probes": {"gh.other": []}},
))
def test_world_overrides_cannot_supply_code_or_new_execution_paths(overrides):
    with pytest.raises(ValueError):
        run(overrides=overrides)


def test_type_strict_dependency_input_matching():
    fixture = world()
    fixture["inputs"]["filters"]["head"] = True
    fixture["probes"]["gh.pr.list"][0]["with_"]["head"] = 1
    with pytest.raises(ValueError, match="Resolved SDK fixture inputs differ"):
        run(overrides=fixture)


def test_missing_public_contract_is_not_manufactured(monkeypatch):
    class MissingRegistry:
        def get_operation(self, reference):
            return None

    monkeypatch.setattr("ordo.connectors.registry.get_public_connector_registry", MissingRegistry)
    with pytest.raises(ValueError, match="published gh.pr.list probe contract"):
        run()


def test_budget_bounds_repeated_adapter_execution(monkeypatch):
    from connectors import _family

    original = _family._adapt_published_handler

    def adapt(*, published, package_name):
        handler = original(published=published, package_name=package_name)
        if published.name != "snippet":
            return handler

        def repeat(resolved, workflow):
            for _ in range(5):
                handler(resolved, workflow)

        return repeat

    monkeypatch.setattr(_family, "_adapt_published_handler", adapt)
    with pytest.raises(ValueError, match="4-call fixture budget"):
        run()


def test_renderer_labels_python_and_never_executes_it(monkeypatch):
    from ordo.help_cli import _append_text_canonical_examples

    def forbidden(*args, **kwargs):
        raise AssertionError("Help display must not verify or execute snippets")

    monkeypatch.setattr("ordo.runtime.help_sdk_snippet_runner.execute_sdk_probe_fragment", forbidden)
    lines = []
    _append_text_canonical_examples(lines, [example()])
    text = "\n".join(lines)
    assert "example_for: python_fragment" in text
    assert "  python:" in text
    assert "  yaml:" not in text
    for line in example()["python"].splitlines():
        assert f"    {line}" in lines


@pytest.mark.parametrize("change", ({"form": "workflow_fragment"}, {"python": ""}, {"yaml": "def run(ctx): pass"}))
def test_registry_prevents_disguised_python_shapes(change):
    from ordo.model.help_snippets import validate_help_snippet_registry

    registry = describe_help_snippets()
    registry["connector.authoring"]["canonical_examples"][0].update(change)
    with pytest.raises(ValueError, match="[Pp]ython|python_fragment"):
        validate_help_snippet_registry(registry)


@pytest.mark.parametrize("as_json", (False, True))
def test_public_describe_publishes_python_without_verification(as_json, monkeypatch, capsys):
    import json
    from ordo.help_cli import main

    def forbidden(*args, **kwargs):
        raise AssertionError("Describe must not execute verification")

    monkeypatch.setattr("ordo.runtime.help_sdk_snippet_runner.execute_sdk_probe_fragment", forbidden)
    args = ["ordo-help", "describe", "connector.authoring"] + (["--json"] if as_json else [])
    monkeypatch.setattr("sys.argv", args)
    assert main() == 0
    output = capsys.readouterr().out
    if as_json:
        payload = json.loads(output)
        assert payload["snippet_coverage"] == "runner_verified"
        assert payload["canonical_examples"] == [example()]
    else:
        assert "python_fragment" in output
        assert "  python:" in output
        assert "ctx.call('gh.pr.list', inputs=ctx.input('filters'))" in output
