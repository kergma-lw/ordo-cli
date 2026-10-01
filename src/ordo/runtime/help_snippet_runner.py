"""Shared verification runner for world-backed help snippets."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import json
from pathlib import Path
import os
import re
import subprocess
import tempfile

import yaml

from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.model.runtime import OperationResult, RuntimeResult, RuntimeStatus
from ordo.routines import load_routine_registry

from . import load_workflow_file, load_workflow_text, validate_workflow_semantics, validate_workflow_text
from .loading import load_yaml_document
from .help_snippet_scaffolds import build_expression_value_scaffold, build_step_field_scaffold, build_step_fragment_scaffold, build_workflow_fragment_scaffold


@dataclass(frozen=True)
class HelpSnippetRunnerResult:
    """Structured result for one world-backed help snippet verification."""

    world_name: str
    insertion_mode: str
    target: str
    workflow_text: str
    effective_world: dict[str, object]
    status: str
    verification_path: str = "validation_only"
    runtime_result: RuntimeResult | None = None
    calls: tuple[dict[str, object], ...] = ()
    python_text: str | None = None
    operation_result: OperationResult | None = None
    graph_result: dict[str, object] | None = None


def verify_help_snippet(
    *,
    snippet: str,
    world: str,
    insertion_mode: str,
    target: str,
    overrides: dict[str, object] | None = None,
) -> HelpSnippetRunnerResult:
    """Verify one help snippet inside a named world and explicit insertion scaffold."""

    worlds = describe_help_snippet_worlds()
    if world not in worlds:
        raise ValueError(f"Unknown snippet world: {world}")
    effective_world = deepcopy(worlds[world])
    if overrides:
        effective_world = _deep_merge(effective_world, overrides)

    if world in {"git-remote-exists", "git-remote-missing"}:
        from ordo.model.help_snippets import _git_remote_workflow
        from .executing import execute_workflow

        if (insertion_mode != "workflow_fragment" or target != "connector.git.remote"
                or snippet != _git_remote_workflow()):
            raise ValueError("Fixture execution accepts only the exact published git.remote workflow")
        workflow = load_workflow_text(snippet, source=f"snippet-execution:{world}")
        inputs = effective_world["inputs"]
        if not isinstance(inputs, dict) or set(inputs) != set(workflow.declared_inputs):
            raise ValueError("Remote fixture inputs must match declared workflow inputs")
        workflow = replace(workflow, inputs=deepcopy(inputs), explicit_input_keys=tuple(inputs))
        report = validate_workflow_semantics(workflow)
        if report.status != RuntimeStatus.OK:
            raise ValueError("Published git.remote workflow failed semantic validation")
        if set(effective_world["probes"]) != {"git.remote"}:
            raise ValueError("Remote execution requires exactly the git.remote fixture")
        calls = []
        provider = normalized_fixture_provider(
            effective_world, references={"git.remote"}, calls=calls, call_budget=12, strict_nulls=True,
        )
        result = execute_workflow(workflow, connector_provider=provider)
        return HelpSnippetRunnerResult(
            world_name=world, insertion_mode=insertion_mode, target=target,
            workflow_text=snippet, effective_world=effective_world, status=result.status.value,
            verification_path="fixture_execution", runtime_result=result, calls=tuple(calls),
        )

    if world in {"gh-actions-direct", "gh-actions-bridge", "gh-actions-null-suite", "gh-actions-no-run"}:
        from ordo.model.help_snippets import GH_ACTIONS_TARGETS, _gh_actions_workflow
        from .executing import execute_workflow

        if (insertion_mode != "workflow_fragment" or target not in GH_ACTIONS_TARGETS
                or snippet != _gh_actions_workflow(bridge=world != "gh-actions-direct")):
            raise ValueError("Fixture execution accepts only the exact published Actions workflow")
        workflow = load_workflow_text(snippet, source=f"snippet-execution:{world}")
        inputs = effective_world["inputs"]
        if not isinstance(inputs, dict) or set(inputs) != set(workflow.declared_inputs):
            raise ValueError("Actions fixture inputs must match declared workflow inputs")
        workflow = replace(workflow, inputs=deepcopy(inputs), explicit_input_keys=tuple(inputs))
        calls = []
        provider = normalized_fixture_provider(
            effective_world, references={"gh.pr.checks", "gh.actions.run", "gh.actions.run.jobs"},
            calls=calls, call_budget=20,
        )
        result = execute_workflow(workflow, connector_provider=provider)
        return HelpSnippetRunnerResult(
            world_name=world, insertion_mode=insertion_mode, target=target,
            workflow_text=snippet, effective_world=effective_world, status=result.status.value,
            verification_path="fixture_execution", runtime_result=result, calls=tuple(calls),
        )

    if world == "gh-pr-create-new-only":
        return _execute_gh_pr_create_snippet(
            snippet=snippet, world=world, insertion_mode=insertion_mode,
            target=target, effective_world=effective_world,
        )

    if world in {"gh-pr-list-no-pr", "gh-pr-list-exactly-one-open", "gh-pr-list-ambiguous-multiple-open",
                 "gh-pr-list-only-closed-history", "gh-pr-list-unknown-metadata"}:
        return _execute_gh_pr_list_snippet(
            snippet=snippet, world=world, insertion_mode=insertion_mode,
            target=target, effective_world=effective_world,
        )

    if world in {"gh-pr-merge-head", "gh-pr-merge-test-merge", "gh-pr-merge-head-context"}:
        return _execute_gh_pr_merge_snippet(
            snippet=snippet, world=world, insertion_mode=insertion_mode,
            target=target, effective_world=effective_world,
        )

    if insertion_mode == "routine_bundle":
        return _verify_routine_bundle_snippet(snippet=snippet, world=world, target=target, effective_world=effective_world)

    if insertion_mode == "graph_bundle":
        from .graphing import build_static_graph, render_static_graph

        if target not in {"state", "command-line.ordo-playbook"}:
            raise ValueError(f"Unsupported graph bundle target: {target}")
        payload = load_yaml_document(snippet, source=f"graph-bundle:{target}:{world}")
        project_bundle = isinstance(payload, dict) and "playbook_text" in payload
        required = ({"playbook_text", "files"} if project_bundle else {"workflows"}) | {"expected_links", "expected_loops"}
        if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - {"expected_text", "expected_structural_links"}:
            raise ValueError("Graph bundle requires workflows or playbook_text/files, expected_links and expected_loops; expected_text is optional")
        workflows = []
        for text in payload.get("workflows", []):
            workflow = load_workflow_text(text)
            # Named world locations define identity; their contents are intentionally
            # absent. This path verifies graph output, never runtime readiness.
            workflow = replace(workflow,
                state_bindings={role: "shared_state" for role in workflow.state_needs},
                states={"shared_state": "/snippet-world/absent-state.json"})
            workflows.append((workflow.workflow, workflow, "/snippet-world"))
        if project_bundle:
            from ordo.playbook import build_playbook_static_graph
            if not isinstance(payload["playbook_text"], str) or not isinstance(payload["files"], dict):
                raise ValueError("Graph playbook bundle requires text and a file-text mapping")
            with tempfile.TemporaryDirectory(prefix="ordo-help-graph-") as directory:
                root = Path(directory)
                for name, text in payload["files"].items():
                    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or not isinstance(text, str):
                        raise ValueError("Graph bundle files must be relative authored text files")
                    destination = root / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(text, encoding="utf-8")
                playbook = root / "ordo.yaml"
                playbook.write_text(payload["playbook_text"], encoding="utf-8")
                graph = build_playbook_static_graph(playbook_path=playbook)
        else:
            graph = build_static_graph(workflows)
        links = sorted({(link["from_workflow"], link["to_workflow"], link["kind"], link["address_identity"])
                        for link in graph["links"]})
        if links != sorted(tuple(link) for link in payload["expected_links"]):
            raise ValueError(f"Graph bundle link mismatch: {links!r}")
        if graph["possible_loop_components"] != payload["expected_loops"]:
            raise ValueError("Graph bundle loop mismatch")
        if "expected_structural_links" in payload:
            actual = sorted({(link["from_workflow"], link["to_workflow"], link["kind"],
                              link["selector_correspondence"], tuple(sorted({r["predicate"] for r in link["requirements"]})))
                             for link in graph["structural_links"]})
            expected = sorted((item["from"], item["to"], item["kind"], item["correspondence"],
                               tuple(sorted(item["requires"]))) for item in payload["expected_structural_links"])
            if actual != expected:
                raise ValueError(f"Graph bundle structural link mismatch: {actual!r}")
        if "expected_text" in payload:
            expected_text = payload["expected_text"]
            if not isinstance(expected_text, str) or render_static_graph(graph) != expected_text.rstrip("\n"):
                raise ValueError("Graph bundle compact text mismatch")
        return HelpSnippetRunnerResult(world_name=world, insertion_mode=insertion_mode, target=target,
            workflow_text=snippet, effective_world=effective_world, status="ok",
            verification_path="static_graph", graph_result=graph)

    if insertion_mode == "state_bundle":
        if target not in {"state", "workflow.state_bindings", "workflow.step.state_set", "workflow.step.state_delete"}:
            raise ValueError(f"Unsupported state bundle target: {target}")
        payload = load_yaml_document(snippet, source=f"snippet-bundle:{target}:{world}")
        if not isinstance(payload, dict) or set(payload) != {"workflow_text", "state_bindings", "expected_diagnostic_codes"}:
            raise ValueError("State bundle must declare workflow_text, state_bindings, and expected_diagnostic_codes")
        workflow_text = payload["workflow_text"]
        bindings = payload["state_bindings"]
        if not isinstance(workflow_text, str) or not isinstance(bindings, dict):
            raise ValueError("State bundle requires workflow text and a role-to-world-state mapping")
        if any(not isinstance(role, str) or not isinstance(name, str) or name not in effective_world["state"] for role, name in bindings.items()):
            raise ValueError("State bundle bindings must reference named world state")
        workflow = load_workflow_text(workflow_text)
        with tempfile.TemporaryDirectory(prefix="ordo-help-state-") as directory:
            states = {}
            for index, (name, document) in enumerate(effective_world["state"].items()):
                path = Path(directory) / f"state-{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                states[name] = str(path)
            workflow = replace(workflow, state_bindings=bindings, states=states)
            report = validate_workflow_semantics(workflow, state_base_dir=directory)
        codes = [diagnostic.code for diagnostic in report.diagnostics]
        if codes != payload["expected_diagnostic_codes"]:
            raise ValueError(f"State bundle diagnostic mismatch: {codes!r}")
        return HelpSnippetRunnerResult(
            world_name=world, insertion_mode=insertion_mode, target=target,
            workflow_text=workflow_text, effective_world=effective_world, status=report.status.value,
        )

    if insertion_mode == "expression_value":
        workflow_text = build_expression_value_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "step_field":
        workflow_text = build_step_field_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "step_fragment":
        workflow_text = build_step_fragment_scaffold(target=target, snippet=snippet)
    elif insertion_mode == "workflow_fragment":
        workflow_text = build_workflow_fragment_scaffold(target=target, snippet=snippet)
    else:
        raise ValueError(f"Unsupported insertion mode: {insertion_mode}")

    report = validate_workflow_text(workflow_text, source=f"snippet-runner:{target}:{world}")
    status = report.status.value if isinstance(report.status, RuntimeStatus) else str(report.status)
    return HelpSnippetRunnerResult(
        world_name=world,
        insertion_mode=insertion_mode,
        target=target,
        workflow_text=workflow_text,
        effective_world=effective_world,
        status=status,
    )


def _validate_normalized_fields(value, schema, *, path, strict_nulls=False):
    """Validate fixture types; legacy worlds permit implicit scalar nulls."""
    if isinstance(schema, str) and " | " in schema:
        variants = schema.split(" | ")
        if value is None and "null" in variants:
            return
        for variant in variants:
            if variant == "null":
                continue
            try:
                _validate_normalized_fields(value, variant, path=path, strict_nulls=True)
                return
            except ValueError:
                pass
        raise ValueError(f"Normalized fixture type differs at {path}")
    if isinstance(schema, dict):
        if not isinstance(value, dict) or set(value) != set(schema):
            raise ValueError(f"Normalized fixture fields differ at {path}")
        for key, child in schema.items():
            _validate_normalized_fields(value[key], child, path=f"{path}.{key}", strict_nulls=strict_nulls)
    elif isinstance(schema, list):
        if not isinstance(value, list) or len(schema) != 1:
            raise ValueError(f"Normalized fixture collection differs at {path}")
        for child in value:
            _validate_normalized_fields(child, schema[0], path=f"{path}[]", strict_nulls=strict_nulls)
    elif value is not None or strict_nulls:
        types = {"string": str, "integer": int, "boolean": bool, "object": dict, "number": (int, float)}
        expected = types.get(schema)
        if expected is None or (type(value) not in expected if isinstance(expected, tuple) else type(value) is not expected):
            raise ValueError(f"Normalized fixture type differs at {path}")


def normalized_fixture_provider(world, *, references, calls, call_budget, strict_nulls=False):
    """Reusable read-only public-operation fixtures; no default/live dispatch.

    This validates normalized fields and exact resolved bindings, not transport
    acquisition or workflow policy. The caller owns canonical source admission.
    """
    from ordo.connectors.registry import get_public_connector_registry
    from .providers import ConnectorProvider
    from .resolution import ResolvedOperation
    from .value_resolution import resolve_runtime_value

    registry = get_public_connector_registry()
    if world.get("actions") or set(world["probes"]) - references:
        raise ValueError("Only allowlisted normalized probe fixtures are supported")
    for reference, fixtures in world["probes"].items():
        contract = registry.get_operation(reference)
        if contract is None or contract.kind != "probe" or len(fixtures) != 1:
            raise ValueError(f"Expected one public probe fixture for {reference}")
        fixture = fixtures[0]
        if set(fixture) - {"with_", "outputs", "status"} or not {"with_", "outputs"} <= set(fixture):
            raise ValueError(f"Unexpected fixture fields for {reference}")
        if not isinstance(fixture["with_"], dict) or set(fixture["with_"]) - set(contract.inputs):
            raise ValueError(f"Unexpected fixture inputs for {reference}")
        for key, value in fixture["with_"].items():
            _validate_normalized_fields(value, contract.inputs[key], path=f"{reference}.with.{key}", strict_nulls=strict_nulls)
        status = fixture.get("status", "ok")
        if status == "ok":
            _validate_normalized_fields(fixture["outputs"], contract.outputs, path=reference, strict_nulls=strict_nulls)
        elif status not in contract.failure_modes or fixture["outputs"] != {}:
            raise ValueError(f"Unsupported failure fixture for {reference}")

    def invoke(resolved, workflow, *, phase):
        if len(calls) >= call_budget:
            raise ValueError("Normalized snippet exceeded its fixture call budget")
        if not isinstance(resolved, ResolvedOperation) or resolved.reference not in references:
            raise ValueError("Only allowlisted materialized probes can use normalized fixtures")
        fixtures = world["probes"].get(resolved.reference, [])
        if len(fixtures) != 1:
            raise ValueError(f"Missing normalized fixture for {resolved.reference}")
        fixture = fixtures[0]
        inputs = resolved.resolved_inputs
        if inputs is None:
            inputs = resolve_runtime_value(resolved.declared_with, workflow)
        if json.dumps(inputs, sort_keys=True) != json.dumps(fixture["with_"], sort_keys=True):
            raise ValueError(f"Resolved fixture inputs differ for {resolved.reference}: {inputs!r}")
        calls.append({"reference": resolved.reference, "phase": phase, "inputs": deepcopy(inputs)})
        return OperationResult(status=fixture.get("status", "ok"), outputs=deepcopy(fixture["outputs"]))

    return ConnectorProvider(
        registry=registry,
        guard_probe=lambda resolved, workflow: invoke(resolved, workflow, phase="probe"),
        step_executor=lambda resolved, workflow: invoke(resolved, workflow, phase="execute"),
    )


def _execute_gh_pr_create_snippet(
    *, snippet: str, world: str, insertion_mode: str, target: str,
    effective_world: dict[str, object],
) -> HelpSnippetRunnerResult:
    """Execute exact create YAML only; fixture dispatch never runs SDK or HTTP."""
    from ordo.connectors.registry import get_public_connector_registry
    from ordo.model.help_snippets import _gh_pr_create_workflow
    from .executing import execute_workflow
    from .providers import ConnectorProvider
    from .resolution import ResolvedOperation
    from .value_resolution import resolve_runtime_value

    if insertion_mode != "workflow_fragment" or target != "connector.gh.pr.create" or snippet != _gh_pr_create_workflow():
        raise ValueError("Fixture execution accepts only the exact published gh PR create workflow")
    workflow = load_workflow_text(snippet, source=f"snippet-execution:{world}")
    inputs = effective_world["inputs"]
    if not isinstance(inputs, dict) or set(inputs) - set(workflow.declared_inputs):
        raise ValueError("Create fixture inputs must be declared workflow inputs")
    workflow = replace(workflow, inputs={**workflow.inputs, **inputs}, explicit_input_keys=tuple(inputs))
    registry = get_public_connector_registry()
    for reference, fields in {
        "gh.pr.list": {"items", "count", "complete"},
        "gh.pr.create": {"repository", "pull_number", "pull_ref", "url", "created", "head_ref", "base_ref"},
        "gh.pr": {"state"},
    }.items():
        contract = registry.get_operation(reference)
        if contract is None or not fields.issubset(contract.outputs):
            raise ValueError(f"Create snippet execution requires the published output contract for {reference}")
    calls: list[dict[str, object]] = []
    submitted = False

    def invoke(resolved, current_workflow, *, phase):
        nonlocal submitted
        if len(calls) >= 20:
            raise ValueError("Create snippet exceeded its 20-call fixture budget")
        if not isinstance(resolved, ResolvedOperation):
            raise ValueError("Create fixture requires a materialized operation")
        reference = resolved.reference
        if reference == "gh.pr.create":
            if phase != "execute" or submitted:
                raise ValueError("Create fixture permits one execution-time submission")
            fixture = effective_world["actions"][reference]
        elif reference in {"gh.pr.list", "gh.pr"}:
            if reference == "gh.pr" and not submitted:
                raise ValueError("Final PR observation requires a create submission")
            fixtures = effective_world["probes"][reference]
            if len(fixtures) != 1:
                raise ValueError("Create execution requires one fixture per observation")
            fixture = fixtures[0]
        else:
            raise ValueError(f"No fixture execution allowed for {reference}")
        if resolved.resolved_inputs is None:
            resolved = replace(resolved, resolved_inputs=resolve_runtime_value(resolved.declared_with, current_workflow))
        if json.dumps(resolved.resolved_inputs, sort_keys=True) != json.dumps(fixture["with_"], sort_keys=True):
            raise ValueError(f"Resolved fixture inputs differ for {reference}: {resolved.resolved_inputs!r}")
        calls.append({"reference": reference, "phase": phase, "inputs": deepcopy(resolved.resolved_inputs)})
        if reference == "gh.pr.create":
            submitted = True
        return OperationResult(status=fixture.get("status", "ok"), outputs=deepcopy(fixture["outputs"]))

    provider = ConnectorProvider(
        registry=registry,
        guard_probe=lambda resolved, workflow: invoke(resolved, workflow, phase="probe"),
        step_executor=lambda resolved, workflow: invoke(resolved, workflow, phase="execute"),
    )
    result = execute_workflow(workflow, connector_provider=provider)
    return HelpSnippetRunnerResult(
        world_name=world, insertion_mode=insertion_mode, target=target,
        workflow_text=snippet, effective_world=effective_world, status=result.status.value,
        verification_path="fixture_execution", runtime_result=result, calls=tuple(calls),
    )


def _execute_gh_pr_list_snippet(
    *, snippet: str, world: str, insertion_mode: str, target: str,
    effective_world: dict[str, object],
) -> HelpSnippetRunnerResult:
    """Bounded observer execution; exact text and strict fixtures, never live dispatch."""
    from ordo.connectors.registry import get_public_connector_registry
    from ordo.model.help_snippets import _gh_pr_list_workflow
    from .executing import execute_workflow
    from .providers import ConnectorProvider
    from .resolution import ResolvedOperation
    from .value_resolution import resolve_runtime_value

    if insertion_mode != "workflow_fragment" or target != "connector.gh.pr.list" or snippet != _gh_pr_list_workflow():
        raise ValueError("Fixture execution accepts only the exact published gh PR list workflow")
    workflow = load_workflow_text(snippet, source=f"snippet-execution:{world}")
    inputs = effective_world["inputs"]
    if not isinstance(inputs, dict) or set(inputs) - set(workflow.declared_inputs):
        raise ValueError("PR list fixture inputs must be declared workflow inputs")
    workflow = replace(workflow, inputs={**workflow.inputs, **inputs}, explicit_input_keys=tuple(inputs))
    registry = get_public_connector_registry()
    contract = registry.get_operation("gh.pr.list")
    fields = {"repository", "head", "head_owner", "base", "state", "items", "count", "complete"}
    if contract is None or not fields.issubset(contract.outputs):
        raise ValueError("PR list snippet execution requires the published output contract for gh.pr.list")
    item_fields = {"number", "url", "state", "draft", "merged", "merged_at", "head_repository", "head_repository_key",
                   "head_owner", "head_ref", "head_sha", "base_repository", "base_ref", "base_sha", "pull_ref"}
    item_schema = contract.outputs["items"]
    if not isinstance(item_schema, list) or len(item_schema) != 1 or not isinstance(item_schema[0], dict) or not item_fields.issubset(item_schema[0]):
        raise ValueError("PR list snippet execution requires the published item identity contract")
    calls: list[dict[str, object]] = []

    def invoke(resolved, current_workflow, *, phase):
        if len(calls) >= 20:
            raise ValueError("PR list snippet exceeded its 20-call fixture budget")
        if not isinstance(resolved, ResolvedOperation) or resolved.reference != "gh.pr.list":
            raise ValueError("Only gh.pr.list fixture execution is allowed")
        if resolved.resolved_inputs is None:
            resolved = replace(resolved, resolved_inputs=resolve_runtime_value(resolved.declared_with, current_workflow))
        fixtures = effective_world["probes"].get(resolved.reference, [])
        if len(fixtures) != 1:
            raise ValueError("PR list execution requires exactly one complete observation fixture")
        fixture = fixtures[0]
        if json.dumps(resolved.resolved_inputs, sort_keys=True) != json.dumps(fixture["with_"], sort_keys=True):
            raise ValueError(f"Resolved fixture inputs differ for gh.pr.list: {resolved.resolved_inputs!r}")
        calls.append({"reference": resolved.reference, "phase": phase, "inputs": deepcopy(resolved.resolved_inputs)})
        return OperationResult(status=fixture.get("status", "ok"), outputs=deepcopy(fixture["outputs"]))

    provider = ConnectorProvider(
        registry=registry,
        guard_probe=lambda resolved, workflow: invoke(resolved, workflow, phase="probe"),
        step_executor=lambda resolved, workflow: invoke(resolved, workflow, phase="execute"),
    )
    result = execute_workflow(workflow, connector_provider=provider)
    return HelpSnippetRunnerResult(
        world_name=world, insertion_mode=insertion_mode, target=target,
        workflow_text=snippet, effective_world=effective_world, status=result.status.value,
        verification_path="fixture_execution", runtime_result=result, calls=tuple(calls),
    )


def _execute_gh_pr_merge_snippet(
    *, snippet: str, world: str, insertion_mode: str, target: str,
    effective_world: dict[str, object],
) -> HelpSnippetRunnerResult:
    """Execute only the published merge family, with no live-provider fallback.

    Canonical-text admission bounds the language (no run, routine, state, profile,
    shell, or arbitrary expression probes). Fixture overrides change data only.
    PR fixtures represent before/after submission, rather than fragile call counts:
    check/preflight may re-observe the same handle before execution reaches it.
    """
    from ordo.connectors.registry import get_public_connector_registry
    from ordo.model.help_snippets import _gh_pr_merge_workflow
    from .executing import execute_workflow
    from .help_snippet_scaffolds import GH_PR_MERGE_TARGETS
    from .providers import ConnectorProvider
    from .resolution import ResolvedOperation
    from .value_resolution import resolve_runtime_value

    context_repository = world == "gh-pr-merge-head-context"
    expected = _gh_pr_merge_workflow(
        test_merge=world == "gh-pr-merge-test-merge", context_repository=context_repository,
    )
    if insertion_mode != "workflow_fragment" or target not in GH_PR_MERGE_TARGETS or snippet != expected:
        raise ValueError("Fixture execution accepts only the exact published gh PR merge workflow")
    workflow = load_workflow_text(snippet, source=f"snippet-execution:{world}")
    inputs = effective_world["inputs"]
    if not isinstance(inputs, dict) or set(inputs) - set(workflow.declared_inputs):
        raise ValueError("Merge fixture inputs must be declared workflow inputs")
    workflow = replace(workflow, inputs={**workflow.inputs, **inputs}, explicit_input_keys=tuple(inputs))
    if context_repository:
        # Runtime context is supplied by composition (normally a profile), not
        # loaded from an invented workflow YAML field.
        contexts = effective_world.get("connector_contexts")
        if contexts != {"gh": {"repository": "acme/mobile-app"}}:
            raise ValueError("Merge context world requires its published literal gh repository")
        workflow = replace(workflow, connector_contexts=deepcopy(contexts))
    calls: list[dict[str, object]] = []
    submitted = False

    def invoke(resolved, _workflow, *, phase):
        nonlocal submitted
        if len(calls) >= 32:
            raise ValueError("Merge snippet exceeded its 32-call fixture budget")
        if not isinstance(resolved, ResolvedOperation):
            raise ValueError("Merge fixture requires a materialized operation")
        reference = resolved.reference
        if reference == "gh.pr.merge":
            if phase != "execute" or submitted:
                raise ValueError("Merge fixture permits exactly one execution-time submission")
            fixture = effective_world["actions"][reference]
        elif reference in {"gh.pr", "gh.pr.checks", "gh.pr.merge.request"}:
            # Preflight passes authored probe bindings to the provider; ordinary
            # execution already materializes them. Resolve the former through
            # the real value resolver before applying the same strict match.
            if resolved.resolved_inputs is None:
                resolved = replace(resolved, resolved_inputs=resolve_runtime_value(resolved.declared_with, _workflow))
            fixtures = effective_world["probes"][reference]
            fixture = fixtures[1 if reference == "gh.pr" and submitted else 0]
        else:
            raise ValueError(f"No fixture execution allowed for {reference}")
        # JSON comparison is type-strict (True must not match integer 1).
        if json.dumps(resolved.resolved_inputs, sort_keys=True) != json.dumps(fixture["with_"], sort_keys=True):
            raise ValueError(f"Resolved fixture inputs differ for {reference}: {resolved.resolved_inputs!r}")
        if context_repository and reference in {"gh.pr.merge", "gh.pr.merge.request"}:
            # Family bootstrap consumes literal context, not runtime expressions.
            # This injected provider checks that boundary without pretending to
            # execute bootstrap/authentication or the actual handler fallback.
            from connectors.gh._repository import normalize_repository_value

            repository = normalize_repository_value(_workflow.connector_contexts["gh"]["repository"])
            if repository is None or fixture["outputs"].get("repository") != repository:
                raise ValueError(f"Fixture output repository differs from gh context for {reference}")
        calls.append({"reference": reference, "phase": phase, "inputs": deepcopy(resolved.resolved_inputs)})
        if reference == "gh.pr.merge":
            submitted = True
        return OperationResult(status=fixture.get("status", "ok"), outputs=deepcopy(fixture["outputs"]))

    registry = get_public_connector_registry()
    # Fixtures cannot manufacture a public output that the connector has not
    # published yet (notably the independently implemented stack observation).
    required_outputs = {
        "gh.pr": {"head_sha", "base_sha", "stack_state", "merged", "merge_commit_sha", "test_merge_state",
                  "test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"},
        "gh.pr.checks": {"head_sha", "base_sha", "expected_head_sha", "target", "commit_sha", "complete",
                         "statuses_complete", "check_runs_complete", "overall_state", "checks",
                         "test_merge_state", "test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"},
        "gh.pr.merge": {"request_id", "state"},
        "gh.pr.merge.request": {"request_id", "state", "message"},
    }
    for reference, fields in required_outputs.items():
        contract = registry.get_operation(reference)
        if contract is None or not fields.issubset(contract.outputs):
            raise ValueError(f"Merge snippet execution requires the published output contract for {reference}: {sorted(fields)}")
    provider = ConnectorProvider(
        registry=registry,
        guard_probe=lambda resolved, workflow: invoke(resolved, workflow, phase="probe"),
        step_executor=lambda resolved, workflow: invoke(resolved, workflow, phase="execute"),
    )
    result = execute_workflow(workflow, connector_provider=provider)
    return HelpSnippetRunnerResult(
        world_name=world, insertion_mode=insertion_mode, target=target,
        workflow_text=snippet, effective_world=effective_world, status=result.status.value,
        verification_path="fixture_execution", runtime_result=result, calls=tuple(calls),
    )


def _verify_routine_bundle_snippet(*, snippet: str, world: str, target: str, effective_world: dict[str, object]) -> HelpSnippetRunnerResult:
    if target != "routine":
        raise ValueError(f"Unsupported routine bundle target: {target}")
    payload = load_yaml_document(snippet, source=f"snippet-bundle:{target}:{world}")
    if not isinstance(payload, dict):
        raise ValueError("Routine bundle snippet must be a mapping")
    routine_id = payload.get("routine_id")
    registry_entry = payload.get("registry_entry")
    implementation_path = payload.get("implementation_path")
    implementation_text = payload.get("implementation_text")
    workflow_step = payload.get("workflow_step")
    sample_args = payload.get("sample_args", {})
    expected_stdout_json = payload.get("expected_stdout_json", {})
    if not isinstance(routine_id, str) or not routine_id:
        raise ValueError("Routine bundle snippet must declare non-empty routine_id")
    if not isinstance(registry_entry, dict):
        raise ValueError("Routine bundle snippet must declare registry_entry object")
    if not isinstance(implementation_path, str) or not implementation_path:
        raise ValueError("Routine bundle snippet must declare implementation_path")
    if not isinstance(implementation_text, str) or not implementation_text:
        raise ValueError("Routine bundle snippet must declare implementation_text")
    if workflow_step is not None and not isinstance(workflow_step, str):
        raise ValueError("Routine bundle workflow_step must be a string when present")
    if not isinstance(sample_args, dict):
        raise ValueError("Routine bundle sample_args must be an object when present")
    if not isinstance(expected_stdout_json, dict):
        raise ValueError("Routine bundle expected_stdout_json must be an object when present")

    with tempfile.TemporaryDirectory(prefix="ordo-help-routine-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        routines_path = tmpdir / ".ordo" / "routines.yaml"
        implementation_file = tmpdir / implementation_path
        routines_path.parent.mkdir(parents=True, exist_ok=True)
        implementation_file.parent.mkdir(parents=True, exist_ok=True)
        routines_payload = {"version": 1, "routines": {routine_id: registry_entry}}
        routines_path.write_text(yaml.safe_dump(routines_payload, sort_keys=False), encoding="utf-8")
        implementation_file.write_text(implementation_text, encoding="utf-8")
        os.chmod(implementation_file, 0o700)

        workflow_text = ""
        status = "ok"
        if isinstance(workflow_step, str) and workflow_step:
            workflow_text = build_step_fragment_scaffold(target="routine", snippet=workflow_step)
            workflow_path = tmpdir / "snippet-routine-bundle.yaml"
            workflow_path.write_text(workflow_text, encoding="utf-8")
            workflow = load_workflow_file(workflow_path, launch_dir=tmpdir)
            report = validate_workflow_semantics(workflow, source=str(workflow_path))
            status = report.status.value if isinstance(report.status, RuntimeStatus) else str(report.status)
            if status != "ok":
                return HelpSnippetRunnerResult(
                    world_name=world,
                    insertion_mode="routine_bundle",
                    target=target,
                    workflow_text=workflow_text,
                    effective_world=effective_world,
                    status=status,
                )

        registry = load_routine_registry(cwd=tmpdir)
        entry = registry.routines[routine_id]
        entrypoint = tmpdir / entry.implementation.argv[0]
        if not entrypoint.exists():
            return HelpSnippetRunnerResult(
                world_name=world,
                insertion_mode="routine_bundle",
                target=target,
                workflow_text=workflow_text,
                effective_world=effective_world,
                status="validation_error",
            )

        argv = _materialize_bundle_argv(entry.implementation.argv, sample_args, project_root=tmpdir)
        completed = subprocess.run(argv, cwd=tmpdir, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return HelpSnippetRunnerResult(
                world_name=world,
                insertion_mode="routine_bundle",
                target=target,
                workflow_text=workflow_text,
                effective_world=effective_world,
                status="execution_error",
            )
        if isinstance(entry.outputs, dict) and entry.outputs.get("mode") == "data":
            observed = load_yaml_document(completed.stdout, source=f"routine-bundle-stdout:{routine_id}")
            if not isinstance(observed, dict):
                return HelpSnippetRunnerResult(
                    world_name=world,
                    insertion_mode="routine_bundle",
                    target=target,
                    workflow_text=workflow_text,
                    effective_world=effective_world,
                    status="execution_error",
                )
            for key, value in expected_stdout_json.items():
                if observed.get(key) != value:
                    return HelpSnippetRunnerResult(
                        world_name=world,
                        insertion_mode="routine_bundle",
                        target=target,
                        workflow_text=workflow_text,
                        effective_world=effective_world,
                        status="execution_error",
                    )

        return HelpSnippetRunnerResult(
            world_name=world,
            insertion_mode="routine_bundle",
            target=target,
            workflow_text=workflow_text,
            effective_world=effective_world,
            status="ok",
        )


_ROUTINE_ARG_TOKEN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _materialize_bundle_argv(argv: tuple[str, ...], sample_args: dict[str, object], *, project_root: Path) -> list[str]:
    materialized: list[str] = []
    for index, item in enumerate(argv):
        token = _ROUTINE_ARG_TOKEN.fullmatch(item)
        if token is not None:
            arg_name = token.group(1)
            materialized.append(str(sample_args[arg_name]))
            continue
        if index == 0:
            materialized.append(str(project_root / item))
            continue
        materialized.append(item)
    return materialized


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged
