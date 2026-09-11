"""Bounded verification of exact published Python through real SDK adapters.

This is not a general Python sandbox or a workflow execution entrypoint. Only
the repository-owned canonical source is compiled. Data overrides cannot supply
code, import targets, handler names, bootstrap implementations, or dependencies.
"""

from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

from ordo.model.help_snippets import _sdk_probe_call_fragment
from ordo.model.help_snippet_worlds import _validate_json_value

if TYPE_CHECKING:
    from .help_snippet_runner import HelpSnippetRunnerResult


def execute_sdk_probe_fragment(
    *, snippet: str, world: str, insertion_mode: str, target: str,
    effective_world: dict[str, object],
) -> "HelpSnippetRunnerResult":
    from .help_snippet_runner import HelpSnippetRunnerResult

    if (snippet != _sdk_probe_call_fragment() or world != "gh-sdk-probe-call"
            or insertion_mode != "sdk_probe_fragment" or target != "connector.authoring"):
        raise ValueError("SDK fixture execution accepts only the exact published Python fragment, world, and target")
    _validate_json_value(effective_world)
    json.dumps(effective_world, allow_nan=False)
    if set(effective_world) != {"name", "summary", "inputs", "state", "probes", "actions"}:
        raise ValueError("SDK world accepts only declared fixture data")
    inputs = effective_world["inputs"]
    if not isinstance(inputs, dict) or set(inputs) - {"filters"}:
        raise ValueError("SDK caller accepts only its declared filters input")
    if "filters" in inputs and (not isinstance(inputs["filters"], dict) or not inputs["filters"]):
        raise ValueError("SDK example requires a nonempty literal JSON filters object")
    if "filters" in inputs and set(inputs["filters"]) - {"repository", "head", "head_owner", "base", "state"}:
        raise ValueError("SDK example accepts only its declared probe filter keys")
    if effective_world["state"] != {} or effective_world["actions"] != {}:
        raise ValueError("SDK world does not execute state or action fixtures")
    probes = effective_world["probes"]
    if not isinstance(probes, dict) or set(probes) != {"gh.pr.list"}:
        raise ValueError("SDK world permits only its gh.pr.list fixture")
    fixtures = probes["gh.pr.list"]
    if not isinstance(fixtures, list) or len(fixtures) != 1:
        raise ValueError("SDK world requires exactly one dependency fixture")
    fixture = fixtures[0]
    if not isinstance(fixture, dict) or set(fixture) - {"with_", "outputs", "status"}:
        raise ValueError("SDK probe accepts only input, output, and status fixture data")
    if not isinstance(fixture.get("with_"), dict) or not isinstance(fixture.get("outputs"), dict):
        raise ValueError("SDK probe requires literal input and output objects")

    # Resolve real contracts before installing the closed synthetic import map.
    from connectors import _family
    from connectors.gh.probes.pr.list import info
    from ordo.connectors.registry import get_public_connector_registry
    from ordo.model.connector import Connector, ConnectorBootstrap
    from ordo.model.workflow import Guard, OperationRef, Workflow
    from ordo.plugin_sdk import OperationOutcome, action, bootstrap, bootstrap_ok
    from .resolution import ResolvedOperation

    contract = get_public_connector_registry().get_operation("gh.pr.list")
    fields = {"repository", "head", "head_owner", "base", "state", "items", "count", "complete"}
    if contract is None or contract.kind != "probe" or not fields.issubset(contract.outputs):
        raise ValueError("SDK snippet requires the published gh.pr.list probe contract")
    if not fields.issubset(fixture["outputs"]):
        raise ValueError("SDK fixture must supply the actual PR-list output shape")
    if not isinstance(fixture["outputs"]["items"], list):
        raise ValueError("SDK PR-list items must be an array")
    item_fields = set(contract.outputs["items"][0])
    if any(not isinstance(item, dict) or not item_fields.issubset(item) for item in fixture["outputs"]["items"]):
        raise ValueError("SDK fixture items must supply the published PR-list identity shape")

    calls: list[dict[str, object]] = []

    def record(reference, phase, values):
        if len(calls) >= 4:
            raise ValueError("SDK snippet exceeded its 4-call fixture budget")
        calls.append({"reference": reference, "phase": phase, "inputs": deepcopy(values)})

    def dependency(ctx):
        # These fixture fields deliberately use real SDK input reads. A missing
        # explicit key raises the SDK's mapped input_error, not a verifier error.
        values = {key: ctx.input(key) for key in ("repository", "head", "head_owner", "base", "state")}
        if ctx.reference != "gh.pr.list":
            raise ValueError("Unexpected SDK dependency reference")
        if json.dumps(values, sort_keys=True) != json.dumps(fixture["with_"], sort_keys=True):
            raise ValueError(f"Resolved SDK fixture inputs differ: {values!r}")
        record(ctx.reference, "sdk_probe", values)
        return OperationOutcome(status=fixture.get("status", "ok"), outputs=deepcopy(fixture["outputs"]))

    # Admission above compares the entire source; exec never sees world data.
    scope = {"__builtins__": {}}
    exec(compile(snippet, "<canonical-sdk-probe-fragment>", "exec"), scope)
    caller = action(name="snippet", handler=scope["run"], inputs={"filters": "object"}, outputs=contract.outputs)
    caller_contract = _family._contract_from_published(caller, package_name="help_snippet.gh.actions")
    dependency_publication = replace(info(), handler=dependency)
    dependency_handler = _family._adapt_published_handler(
        published=dependency_publication, package_name="help_snippet.gh.probes")
    caller_handler = _family._adapt_published_handler(published=caller, package_name="help_snippet.gh.actions")

    def lookup(name):
        if name != "pr.list":
            raise ValueError(f"No SDK fixture dependency allowed for {name}")
        return dependency_handler

    def forbid_action(name):
        raise ValueError(f"No SDK action dependency allowed for {name}")

    def boot(ctx):
        record("gh.bootstrap", "fixture_bootstrap", ctx.family_input())
        return bootstrap_ok(context={"repository": "acme/mobile-app"})

    family = SimpleNamespace(
        get_connector=lambda: Connector(namespace="gh", bootstrap=ConnectorBootstrap(), operations=(contract,)),
        get_probe_handler=lookup, get_action_handler=forbid_action,
    )
    bootstrap_module = SimpleNamespace(BOOTSTRAP=ConnectorBootstrap(), info=lambda: bootstrap(handler=boot))

    def closed_import(name):
        if name == "help_snippet.gh":
            return family
        if name == "help_snippet.gh.bootstrap":
            return bootstrap_module
        raise ValueError(f"No SDK fixture import allowed for {name}")

    workflow = Workflow(
        version=0, workflow="sdk-snippet-host", steps=(),
        inputs={"state": "must-not-inherit", "head": "must-not-evaluate"},
        guards=(Guard(operation=OperationRef("gh.pr.list", with_={"state": "must-not-inherit"})),),
    )
    resolved = ResolvedOperation("gh.snippet", "gh", caller_contract, "public", declared_with={}, resolved_inputs=deepcopy(inputs))
    with patch.object(_family, "import_module", closed_import):
        result = caller_handler(resolved, workflow)
    return HelpSnippetRunnerResult(
        world_name=world, insertion_mode=insertion_mode, target=target,
        workflow_text="", python_text=snippet, effective_world=effective_world,
        status=result.status, verification_path="sdk_fixture_execution",
        operation_result=result, calls=tuple(calls),
    )
