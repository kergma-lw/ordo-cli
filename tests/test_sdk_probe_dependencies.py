"""Exercise dependency dispatch through real SDK adapters, without external IO."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess

import pytest

from connectors import _family
from ordo.model.connector import Connector, ConnectorBootstrap
from ordo.model.workflow import Guard, OperationRef, Workflow
from ordo.plugin_sdk import action, bootstrap, bootstrap_ok, ok, probe
from ordo.runtime.resolution import ResolvedOperation


@pytest.fixture
def family(monkeypatch):
    def build(*publications):
        contracts = {
            p.name: _family._contract_from_published(p, package_name=f"sdk_test.gh.{p.kind}s")
            for p in publications
        }
        handlers = {
            p.name: _family._adapt_published_handler(published=p, package_name=f"sdk_test.gh.{p.kind}s")
            for p in publications
        }
        lookups = []
        bootstrap_inputs = []

        def lookup(name):
            assert name in handlers, f"Unregistered dependency: {name}"
            lookups.append(name)
            return handlers[name]

        def boot(ctx):
            bootstrap_inputs.append(ctx.family_input())
            return bootstrap_ok(context={"repository": "owner/repo"}, raw={"command_working_directory": "/stub/repo"})

        module = SimpleNamespace(
            get_connector=lambda: Connector(namespace="gh", bootstrap=ConnectorBootstrap(), operations=tuple(contracts.values())),
            get_probe_handler=lookup,
            get_action_handler=lookup,
        )
        bootstrap_module = SimpleNamespace(BOOTSTRAP=ConnectorBootstrap(), info=lambda: bootstrap(handler=boot))

        def import_module(name):
            assert name in ("sdk_test.gh", "sdk_test.gh.bootstrap"), f"External family import: {name}"
            return module if name == "sdk_test.gh" else bootstrap_module

        monkeypatch.setattr(_family, "import_module", import_module)

        def invoke(name="caller", workflow=None, inputs=None):
            workflow = workflow or Workflow(version=0, workflow="sdk-dependencies", guards=(), steps=(), connector_contexts={"gh": {"repo": "raw/repo"}})
            resolved = ResolvedOperation(f"gh.{name}", "gh", contracts[name], "public", declared_with=inputs or {})
            return handlers[name](resolved, workflow)

        return SimpleNamespace(invoke=invoke, lookups=lookups, bootstrap_inputs=bootstrap_inputs, module=module, handlers=handlers)

    monkeypatch.setattr(subprocess, "run", Mock(side_effect=AssertionError("Unexpected subprocess")))
    return build


@pytest.mark.parametrize("name", ["gh.pr.list", "pr.list"])
@pytest.mark.parametrize("caller_kind", [probe, action])
def test_dotted_probe_inputs_are_literal_isolated_and_repeatable(family, name, caller_kind):
    payload = {"query": "${inputs.query}", "nested": {"items": ["${inputs.query}", "{{ inputs.query }}", "state.repo[key]", {"format": "{value}", "args": {"value": "${inputs.query}"}}]}, "null": None}
    original = deepcopy(payload)
    observed = []

    def dependency(ctx):
        observed.append(deepcopy(ctx.input("nested")))
        assert ctx.input("query") == "${inputs.query}"
        assert ctx.input("null") is None
        assert ctx.optional_input("inherited") is None
        assert ctx.reference == "gh.pr.list"
        assert ctx.bootstrap().raw["command_working_directory"] == "/stub/repo"
        ctx.input("nested")["items"].append("mutated")
        return ok(outputs={"value": True}, raw={"dependency": "preserved"})

    f = family(caller_kind(name="caller", handler=lambda ctx: ctx.call(name, inputs=payload)), probe(name="pr.list", handler=dependency))
    workflow = Workflow(version=0, workflow="sdk-dependencies", inputs={"query": "evaluated", "inherited": "workflow"},
                        guards=(Guard(operation=OperationRef("gh.pr.list", with_={"inherited": "workflow"})),), steps=(),
                        connector_contexts={"gh": {"repo": "raw/repo"}})
    before = deepcopy(workflow)
    for _ in range(3):
        result = f.invoke(workflow=workflow, inputs={"inherited": "caller"})
        assert result.status == "ok"
        assert result.raw == {"dependency": "preserved", "bootstrap": {"namespace": "gh", "status": "ok", "context": {"repository": "owner/repo"}}}
    assert observed == [original["nested"]] * 3
    assert payload == original
    assert workflow == before
    assert f.lookups == ["pr.list"] * 3
    assert f.bootstrap_inputs == [{"repo": "raw/repo"}] * 6


@pytest.mark.parametrize("inputs", [None, {}])
@pytest.mark.parametrize("name", ["branch", "gh.branch", "repo", "gh.repo", "pr.list", "gh.pr.list"])
def test_empty_inputs_preserve_legacy_workflow_lookup(family, inputs, name):
    local = name.removeprefix("gh.")
    f = family(probe(name="caller", handler=lambda ctx: ctx.call(name, inputs=inputs)),
               probe(name=local, handler=lambda ctx: ok(outputs={"value": ctx.input("query")})))
    workflow = Workflow(version=0, workflow="legacy", inputs={"query": "resolved"},
                        guards=(Guard(operation=OperationRef(f"gh.{local}", with_={"query": "${inputs.query}"})),), steps=())
    assert f.invoke(workflow=workflow).outputs == {"value": "resolved"}


@pytest.mark.parametrize("name", ["git.branch", "git.pr.list", "pr.missing", "gh.missing"])
def test_unknown_and_cross_family_calls_reject_before_handler_lookup(family, name):
    dependency = Mock(side_effect=AssertionError("Must not execute"))
    f = family(probe(name="caller", handler=lambda ctx: ctx.call(name, inputs={"x": 1})),
               probe(name="branch", handler=dependency), probe(name="list", handler=dependency))
    result = f.invoke()
    assert result.status == "execution_error"
    assert name in result.summary
    assert "family 'gh'" in result.summary
    assert f.lookups == []
    dependency.assert_not_called()


@pytest.mark.parametrize("inputs", [None, {}, {"x": 1}])
def test_probe_cannot_execute_action_even_without_inputs(family, inputs):
    mutation = Mock(side_effect=AssertionError("Hidden mutation"))
    f = family(probe(name="caller", handler=lambda ctx: ctx.call("gh.pr.close", inputs=inputs)), action(name="pr.close", handler=mutation))
    result = f.invoke()
    assert result.status == "execution_error"
    assert "cannot call action" in result.summary
    assert f.lookups == []
    mutation.assert_not_called()


@pytest.mark.parametrize("inputs", [None, {}, {"x": 1}])
def test_action_dependency_keeps_only_legacy_no_input_behavior(family, inputs):
    mutation = Mock(return_value=ok())
    f = family(action(name="caller", handler=lambda ctx: ctx.call("pr.close", inputs=inputs)), action(name="pr.close", handler=mutation))
    result = f.invoke()
    if inputs:
        assert result.status == "execution_error"
        assert "only for probes" in result.summary
        mutation.assert_not_called()
    else:
        assert result.status == "ok"
        mutation.assert_called_once()


def test_explicit_inputs_do_not_fill_missing_required_key_from_workflow(family):
    f = family(probe(name="caller", handler=lambda ctx: ctx.call("pr.list", inputs={"query": "literal"})),
               probe(name="pr.list", handler=lambda ctx: ok(outputs={"value": ctx.input("missing")})))
    workflow = Workflow(version=0, workflow="isolated", guards=(Guard(operation=OperationRef("gh.pr.list", with_={"missing": "leaked"})),), steps=())
    result = f.invoke(workflow=workflow)
    assert result.status == "input_error"
    assert result.diagnostics[0].code == "operation.input_missing"
    assert result.diagnostics[0].details == {"reference": "gh.pr.list", "input": "missing"}


def test_dependency_command_failure_preserves_diagnostics_raw_and_bootstrap(family, monkeypatch):
    def dependency(ctx):
        ctx.command(["gh", "pr", "list", ctx.input("query")], failures={"nonzero": "probe_failed"})
        raise AssertionError("Command failure must stop the handler")

    f = family(probe(name="caller", handler=lambda ctx: ctx.call("gh.pr.list", inputs={"query": "inputs.query"})), probe(name="pr.list", handler=dependency))
    command = Mock(return_value=subprocess.CompletedProcess([], 9, stdout="", stderr="stub failure"))
    monkeypatch.setattr(subprocess, "run", command)
    result = f.invoke()
    assert result.status == "probe_failed"
    assert result.diagnostics[0].code == "operation.command_failed"
    assert result.diagnostics[0].details["reference"] == "gh.pr.list"
    assert result.raw["returncode"] == 9
    assert result.raw["stderr"] == "stub failure"
    assert result.raw["bootstrap"]["namespace"] == "gh"
    command.assert_called_once_with(["gh", "pr", "list", "inputs.query"], capture_output=True, text=True, check=False, cwd="/stub/repo")


def test_missing_dependency_handler_is_visible(family):
    f = family(probe(name="caller", handler=lambda ctx: ctx.call("pr.list", inputs={"x": 1})), probe(name="pr.list", handler=lambda ctx: ok()))
    f.module.get_probe_handler = lambda name: None
    result = f.invoke()
    assert result.status == "execution_error"
    assert "does not have a concrete handler" in result.summary


@pytest.mark.parametrize("name", ["gh.pr.list", "pr.list"])
def test_real_pr_list_publication_receives_explicit_inputs(family, monkeypatch, name):
    from connectors.gh.probes.pr.list import info

    f = family(probe(name="caller", handler=lambda ctx: ctx.call(name, inputs={"repository": "owner/repo", "state": "all", "base": "${inputs.base}"})), info())
    command = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="HTTP/2.0 200 OK\n\n[]", stderr=""))
    monkeypatch.setattr(subprocess, "run", command)
    for _ in range(2):
        result = f.invoke()
        assert result.status == "ok"
        assert result.outputs["complete"] is True
        assert result.outputs["base"] == "${inputs.base}"
    assert command.call_count == 2
    assert command.call_args.args[0] == ["gh", "api", "--hostname", "github.com", "--method", "GET", "--include", "/repos/owner/repo/pulls?state=all&per_page=100&base=%24%7Binputs.base%7D&page=1"]


@pytest.mark.parametrize("mode", ["check", "review", "plan", "run", "explain", "next"])
def test_dependency_reads_across_modes_do_not_execute_actions(family, mode, tmp_path, capsys):
    import json
    from unittest.mock import patch

    from ordo.cli import main
    from ordo.model.connector import ConnectorRegistry
    from ordo.model.runtime import RuntimeStatus
    from ordo.model.workflow import Step
    from ordo.runtime import check_workflow, review_workflow, plan_workflow, execute_workflow, explain_workflow
    from ordo.runtime.providers import ConnectorProvider

    mutation = Mock(return_value=ok())
    f = family(
        probe(name="caller", outputs={"value": "boolean"}, handler=lambda ctx: ctx.call("gh.pr.list", inputs={"literal": "${inputs.missing}"})),
        probe(name="pr.list", outputs={"value": "boolean"}, handler=lambda ctx: ok(outputs={"value": ctx.input("literal") == "${inputs.missing}"})),
        action(name="mutate", handler=mutation),
    )
    def dispatch(resolved, workflow):
        assert resolved.reference in ("gh.caller", "gh.mutate")
        return f.handlers[resolved.operation.name](resolved, workflow)

    provider = ConnectorProvider(registry=ConnectorRegistry(connectors=(f.module.get_connector(),)), guard_probe=dispatch, step_executor=dispatch)
    workflow = Workflow(version=0, workflow="sdk-modes", guards=(Guard(expr="gh.caller.value"),),
                        steps=(Step(name="mutate", operation=OperationRef("gh.mutate")),))
    if mode == "next":
        entry = SimpleNamespace(playbook_path=tmp_path / "ordo.yaml", workflow_name=workflow.workflow,
                                workflow_description="SDK dependency", workflow_category="inspect", workflow_when="Inspect", working_directory=tmp_path)
        activated = SimpleNamespace(workflow=workflow, profile=None, working_directory=tmp_path, diagnostics=())
        with (patch("sys.argv", ["ordo-playbook", "next", "--json"]),
              patch("ordo.cli.list_playbook_workflows", return_value=(entry,)),
              patch("ordo.cli.inspect_playbook_workflow", return_value=entry),
              patch("ordo.cli.activate_playbook", return_value=activated),
              patch("ordo.cli.explain_workflow", side_effect=lambda workflow, **kw: explain_workflow(workflow, connector_provider=provider, **kw))):
            assert main() == 0
        assert json.loads(capsys.readouterr().out)["best_candidate"]["allowed"] is True
    else:
        result = dict(check=check_workflow, review=review_workflow, plan=plan_workflow, run=execute_workflow, explain=explain_workflow)[mode](workflow, connector_provider=provider)
        assert result.status == RuntimeStatus.OK
    assert f.lookups and set(f.lookups) == {"pr.list"}
    assert mutation.call_count == (1 if mode == "run" else 0)
