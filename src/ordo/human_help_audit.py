"""Deterministic structural coverage audit for canonical human-help migration."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ordo import help_cli
from ordo.model.human import HumanDeclaration, validate_human_mapping


_ROOT = Path(__file__).resolve().parents[2]
_RENDERER_SOURCES = ("src/ordo/help_cli.py", "tools/build_help_site_docs.py")


ConsumerCoverage = tuple[str, ...]
ConsumerCheck = Callable[..., None]


@dataclass(frozen=True)
class HumanHelpSurface:
    """One public help surface and the source that owns its human content."""

    handle: str
    migration_status: str
    owner: str
    declared_consumers: ConsumerCoverage
    builder: Callable[[], dict[str, Any]] | None = None
    consumer_checks: dict[str, ConsumerCheck] | None = None
    expected_source_paths: tuple[str, ...] = ()
    declarations: Callable[[], tuple[HumanDeclaration, ...]] | None = None
    site_boundary: str | None = None


# This inventory deliberately identifies source owners and route coverage only.
# Human prose remains beside its domain contract and is never copied here.
def _verify_human_renderer(payload: dict[str, Any], renderer: Callable[[dict[str, Any]], str]) -> None:
    """Prove a renderer reads canonical human content rather than contract fields."""

    changed = deepcopy(payload)
    changed["human"]["title"] = "canonical human sentinel"
    changed["audit_contract_metadata"] = "contract metadata sentinel"
    rendered = renderer(changed)
    if "canonical human sentinel" not in rendered:
        raise ValueError("consumer did not render canonical human content")
    if "contract metadata sentinel" in rendered:
        raise ValueError("consumer rendered contract metadata instead of human content")


def _text_check(renderer: Callable[[dict[str, Any]], str]) -> ConsumerCheck:
    return lambda payload, _prepared_index=None: _verify_human_renderer(payload, renderer)


def _site_check(renderer: Callable[[dict[str, Any]], str]) -> ConsumerCheck:
    return lambda payload, _prepared_index=None: _verify_human_renderer(payload, renderer)


def _root_site_renderer(payload: dict[str, Any]) -> str:
    from tools.build_help_site_docs import render_root_index

    return render_root_index(payload, [], [])


def _site_human_renderer(payload: dict[str, Any]) -> str:
    from tools.build_help_site_docs import render_human_topic

    return render_human_topic(payload)


def _search_audit_payload() -> dict[str, Any]:
    """Return the search renderer's fixed fields without rebuilding its catalog."""

    return {
        "document_kind": "search_results",
        "query": "help",
        "topics": [],
        "facts": [],
        "operations": [],
        "human": help_cli.human_content(help_cli.SEARCH_HUMAN, owner="search"),
    }


def _search_check(handle: str) -> ConsumerCheck:
    def check(payload: dict[str, Any], prepared_index: object | None = None) -> None:
        if prepared_index is None:
            raise ValueError("audit did not prepare the search index")
        handle_token = handle.replace("-", "").replace(".", "")
        human_sentinel = f"qzxhsearchhuman{handle_token}sentinel"
        metadata_sentinel = f"qzxhsearchcontract{handle_token}sentinel"
        matched = help_cli.build_search_response(human_sentinel, prepared_index=prepared_index)
        if not any(item["name"] == handle for item in matched["topics"]):
            raise ValueError("search did not index canonical human content")
        technical = help_cli.build_search_response(metadata_sentinel, prepared_index=prepared_index)
        if any(item["name"] == handle for item in technical["topics"]):
            raise ValueError("search indexed contract metadata instead of human content")

    return check


def _focused_search_check(handle: str) -> ConsumerCheck:
    """Prove focused search indexes the target declaration, never node metadata."""

    def check(payload: dict[str, Any], prepared_index: object | None = None) -> None:
        if prepared_index is None:
            raise ValueError("audit did not prepare the search index")
        human_sentinel = f"qzxhfocusedhuman{handle.replace('.', '')}"
        metadata_sentinel = f"qzxhfocusedmetadata{handle.replace('.', '')}"
        readable = help_cli.build_search_response(human_sentinel, prepared_index=prepared_index)
        technical = help_cli.build_search_response(metadata_sentinel, prepared_index=prepared_index)
        if not any(item["name"] == handle for item in readable["facts"]):
            raise ValueError("search did not index focused canonical human content")
        if any(item["name"] == handle for item in technical["facts"]):
            raise ValueError("search indexed focused contract metadata instead of human content")

    return check


def _prepare_audit_search_index(inventory: Sequence[HumanHelpSurface]) -> object:
    """Build one isolated sentinel index for all default audit search checks."""

    from unittest.mock import patch

    overrides: dict[str, dict[str, Any]] = {}
    declarations = help_cli.focused_describe_declarations()
    for surface in inventory:
        if "search" not in surface.declared_consumers:
            continue
        if surface.handle.startswith("describe."):
            handle = surface.handle.removeprefix("describe.")
            payload = surface.builder() if surface.builder is not None else None
            if payload is None:
                continue
            changed = deepcopy(payload)
            sentinel = f"qzxhfocusedhuman{handle.replace('.', '')}"
            changed["human"]["sections"].append({"heading": "Audit", "items": [sentinel]})
            declaration = declarations[handle]
            declarations[handle] = HumanDeclaration(changed["human"], declaration.filename)
            continue
        if surface.handle == "search":
            payload = _search_audit_payload()
        else:
            payload = surface.builder() if surface.builder is not None else None
        if payload is None:
            continue
        changed = deepcopy(payload)
        token = surface.handle.replace("-", "").replace(".", "")
        if not changed["human"]["sections"]:
            changed["human"]["sections"].append({"heading": "Audit", "items": []})
        changed["human"]["sections"][0].setdefault("items", []).append(
            f"qzxhsearchhuman{token}sentinel",
        )
        changed["audit_contract_metadata"] = f"qzxhsearchcontract{token}sentinel"
        overrides[surface.handle] = changed
    with patch.object(help_cli, "focused_describe_declarations", return_value=declarations):
        return help_cli._build_search_index(
            human_surfaces=overrides, context=help_cli._HelpResponseContext(),
        )


def _source_paths(*paths: str) -> tuple[str, ...]:
    return tuple(str((_ROOT / path).resolve()) for path in paths)


def _model_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.model.discovery_catalog import MODEL_HUMAN
    from ordo.model.playbook_contract import PLAYBOOK_HUMAN
    from ordo.model.profile_contract import PROFILE_HUMAN
    from ordo.model.routine_contract import ROUTINE_HUMAN
    from ordo.model.state_contract import STATE_HUMAN
    from ordo.model.workflow_contract import WORKFLOW_HUMAN

    return (MODEL_HUMAN, WORKFLOW_HUMAN, PLAYBOOK_HUMAN, PROFILE_HUMAN, STATE_HUMAN, ROUTINE_HUMAN)


def _feature_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.model.connector import CONNECTOR_FEATURE_HUMAN
    from ordo.model.discovery_catalog import FEATURES_HUMAN
    from ordo.model.playbook_contract import PLAYBOOK_FEATURE_HUMAN
    from ordo.model.profile_contract import PROFILE_FEATURE_HUMAN
    from ordo.model.routine_contract import ROUTINE_FEATURE_HUMAN
    from ordo.model.state_contract import STATE_FEATURE_HUMAN
    from ordo.model.workflow_contract import WORKFLOW_FEATURE_HUMANS

    return (
        FEATURES_HUMAN, PLAYBOOK_FEATURE_HUMAN, PROFILE_FEATURE_HUMAN, *WORKFLOW_FEATURE_HUMANS.values(),
        STATE_FEATURE_HUMAN, ROUTINE_FEATURE_HUMAN, CONNECTOR_FEATURE_HUMAN,
    )


def _capability_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.runtime.capabilities import NEGATIVE_RULES, RUNTIME_CAPABILITIES

    return (
        help_cli.capabilities_human(help_cli.describe_capabilities()),
        *(item.human_declaration() for item in RUNTIME_CAPABILITIES),
        *(item.human_declaration() for item in NEGATIVE_RULES),
    )


def _workflow_rule_declarations() -> tuple[HumanDeclaration, ...]:
    return (help_cli.workflow_rules_human([dict(rule) for rule in help_cli.WORKFLOW_AUTHORING_RULES]),)


def _operations_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.model.connector import operations_catalog_human

    return (operations_catalog_human(help_cli.describe_operations()["connectors"]),)


def _examples_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.model.examples_catalog import examples_catalog_human

    return (examples_catalog_human(help_cli.describe_examples_catalog()["examples"]),)


def _snippet_coverage_declarations() -> tuple[HumanDeclaration, ...]:
    from ordo.model.help_snippets import snippet_coverage_human

    payload = help_cli.build_snippet_coverage_response()
    return (snippet_coverage_human(payload["handles"], payload["summary"]["coverage_counts"]),)


def _focused_describe_surfaces() -> tuple[HumanHelpSurface, ...]:
    """Inventory every public focused target from its source-owned declaration."""

    context = help_cli._HelpResponseContext()
    surfaces: list[HumanHelpSurface] = []
    for handle, declaration in sorted(help_cli.focused_describe_declarations().items()):
        def builder(handle: str = handle) -> dict[str, Any]:
            payload = help_cli._focused_target_payload(handle, context=context)
            if payload is None:
                raise ValueError(f"public focused target {handle} does not resolve")
            return payload

        surfaces.append(HumanHelpSurface(
            handle=f"describe.{handle}",
            migration_status="migrated",
            owner=f"focused.{handle}",
            declared_consumers=("text", "search"),
            builder=builder,
            consumer_checks={
                "text": _text_check(help_cli._render_human),
                "search": _focused_search_check(handle),
            },
            expected_source_paths=(declaration.filename,),
            declarations=lambda declaration=declaration: (declaration,),
            site_boundary="CLI-only: focused describe requires a target and has no generated site page.",
        ))
    return tuple(surfaces)


def _operation_surfaces() -> tuple[HumanHelpSurface, ...]:
    """Inventory every published focused operation independently."""

    surfaces: list[HumanHelpSurface] = []
    for connector in help_cli.get_public_connector_registry().list_connectors():
        for operation in connector.operations:
            reference = f"{connector.namespace}.{operation.name}"
            declaration = operation.human_declaration()
            surfaces.append(HumanHelpSurface(
                handle=f"operation.{reference}",
                migration_status="migrated",
                owner=f"operation.{reference}",
                declared_consumers=("text", "site", "search"),
                builder=lambda reference=reference: help_cli.build_operation_response(reference),  # type: ignore[arg-type]
                consumer_checks={
                    "text": _text_check(help_cli.render_operation_text),
                    "site": _site_check(_site_human_renderer),
                    "search": _search_check(f"operation.{reference}"),
                },
                expected_source_paths=(declaration.filename,),
                declarations=lambda operation=operation: (operation.human_declaration(),),
            ))
    return tuple(surfaces)


def _renderer_source_findings() -> list[str]:
    findings: list[str] = []
    for relative_path in _RENDERER_SOURCES:
        tree = ast.parse((_ROOT / relative_path).read_text(encoding="utf-8"), filename=relative_path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id.endswith("_HUMAN") for target in targets):
                    findings.append(f"renderer defines inline human mapping: {relative_path}:{node.lineno}")
            if isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id == "declare_human"
                or isinstance(node.func, ast.Attribute) and node.func.attr == "declare_human"
            ):
                findings.append(f"renderer defines human declaration: {relative_path}:{node.lineno}")
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value == "human" and isinstance(value, ast.Dict):
                        findings.append(f"renderer defines inline human mapping: {relative_path}:{node.lineno}")
    return findings


HUMAN_HELP_SURFACES: tuple[HumanHelpSurface, ...] = (
    HumanHelpSurface("root", "migrated", "ordo.model.discovery_catalog.ROOT_HUMAN", ("text", "site", "search"), help_cli.build_root_response, {"text": _text_check(help_cli.render_root_text), "site": _site_check(_root_site_renderer), "search": _search_check("root")}, _source_paths("src/ordo/model/discovery_catalog.py"), lambda: (__import__("ordo.model.discovery_catalog", fromlist=["ROOT_HUMAN"]).ROOT_HUMAN,)),
    HumanHelpSurface("features", "migrated", "domain_contracts.feature_clusters", ("text", "site", "search"), help_cli.build_features_response, {"text": _text_check(help_cli.render_features_text), "site": _site_check(_site_human_renderer), "search": _search_check("features")}, _source_paths("src/ordo/model/discovery_catalog.py", "src/ordo/model/workflow_contract.py", "src/ordo/model/playbook_contract.py", "src/ordo/model/profile_contract.py", "src/ordo/model/state_contract.py", "src/ordo/model/routine_contract.py", "src/ordo/model/connector.py"), _feature_declarations),
    HumanHelpSurface("overview", "migrated", "ordo.model.discovery_catalog.OVERVIEW_HUMAN", ("text", "site", "search"), help_cli.build_overview_response, {"text": _text_check(help_cli.render_overview_text), "site": _site_check(_site_human_renderer), "search": _search_check("overview")}, _source_paths("src/ordo/model/discovery_catalog.py"), lambda: (__import__("ordo.model.discovery_catalog", fromlist=["OVERVIEW_HUMAN"]).OVERVIEW_HUMAN,)),
    HumanHelpSurface("model", "migrated", "domain_contracts.human", ("text", "site", "search"), help_cli.build_model_response, {"text": _text_check(help_cli.render_model_text), "site": _site_check(_site_human_renderer), "search": _search_check("model")}, _source_paths("src/ordo/model/discovery_catalog.py", "src/ordo/model/workflow_contract.py", "src/ordo/model/playbook_contract.py", "src/ordo/model/profile_contract.py", "src/ordo/model/state_contract.py", "src/ordo/model/routine_contract.py"), _model_declarations),
    HumanHelpSurface("workflow-rules", "migrated", "ordo.runtime.authoring_human.workflow_rules_human", ("text", "site", "search"), help_cli.build_workflow_rules_response, {"text": _text_check(help_cli.render_workflow_rules_text), "site": _site_check(_site_human_renderer), "search": _search_check("workflow-rules")}, _source_paths("src/ordo/runtime/authoring_human.py"), _workflow_rule_declarations),
    HumanHelpSurface("capabilities", "migrated", "ordo.runtime.capabilities.capabilities_human", ("text", "site", "search"), help_cli.build_capabilities_response, {"text": _text_check(help_cli.render_capabilities_text), "site": _site_check(_site_human_renderer), "search": _search_check("capabilities")}, _source_paths("src/ordo/runtime/capabilities.py"), _capability_declarations),
    HumanHelpSurface("command-line", "migrated", "ordo.model.command_line.COMMAND_LINE_HUMAN", ("text", "site", "search"), help_cli.build_command_line_response, {"text": _text_check(help_cli.render_command_line_text), "site": _site_check(_site_human_renderer), "search": _search_check("command-line")}, _source_paths("src/ordo/model/command_line.py"), lambda: (__import__("ordo.model.command_line", fromlist=["COMMAND_LINE_HUMAN"]).COMMAND_LINE_HUMAN,)),
    HumanHelpSurface("operations", "migrated", "ordo.model.connector.OPERATIONS_HUMAN", ("text", "site", "search"), help_cli.build_operations_response, {"text": _text_check(help_cli.render_operations_text), "site": _site_check(_site_human_renderer), "search": _search_check("operations")}, _source_paths("src/ordo/model/connector.py"), _operations_declarations),
    HumanHelpSurface("examples", "migrated", "ordo.model.examples_catalog.examples_catalog_human", ("text", "site", "search"), help_cli.build_examples_response, {"text": _text_check(help_cli.render_examples_text), "site": _site_check(_site_human_renderer), "search": _search_check("examples")}, _source_paths("src/ordo/model/examples_catalog.py"), _examples_declarations),
    HumanHelpSurface("snippet-coverage", "migrated", "ordo.model.help_snippets.snippet_coverage_human", ("text", "search"), help_cli.build_snippet_coverage_response, {"text": _text_check(help_cli.render_snippet_coverage_text), "search": _search_check("snippet-coverage")}, _source_paths("src/ordo/model/help_snippets.py"), _snippet_coverage_declarations),
    HumanHelpSurface("search", "migrated", "ordo.model.discovery_catalog.SEARCH_HUMAN", ("text", "search"), _search_audit_payload, {"text": _text_check(help_cli.render_search_text), "search": _search_check("search")}, _source_paths("src/ordo/model/discovery_catalog.py"), lambda: (__import__("ordo.model.discovery_catalog", fromlist=["SEARCH_HUMAN"]).SEARCH_HUMAN,)),
)

_VALID_STATUSES = frozenset({"migrated", "unmigrated"})
_VALID_CONSUMERS = frozenset({"text", "site", "search"})


def build_human_help_coverage_report(
    inventory: Sequence[HumanHelpSurface] = HUMAN_HELP_SURFACES,
) -> dict[str, object]:
    """Report migration structure without making any claim about prose quality."""

    default_inventory = inventory is HUMAN_HELP_SURFACES
    inventory = (*inventory, *_operation_surfaces(), *_focused_describe_surfaces()) if default_inventory else tuple(inventory)
    prepared_search_index = _prepare_audit_search_index(inventory) if default_inventory else None
    handles = [surface.handle for surface in inventory]
    duplicate_handles = {handle for handle in handles if handles.count(handle) > 1}
    surfaces: list[dict[str, object]] = []
    failed = False

    for surface in sorted(inventory, key=lambda item: item.handle):
        findings: list[str] = []
        if not surface.handle or surface.handle in duplicate_handles:
            findings.append("inventory handle must be unique and non-empty")
        if surface.migration_status not in _VALID_STATUSES:
            findings.append("inventory migration status must be migrated or unmigrated")
        if not surface.owner.strip():
            findings.append("inventory owner must be declared")
        if not surface.declared_consumers:
            findings.append("inventory must declare at least one consumer")
        elif any(consumer not in _VALID_CONSUMERS for consumer in surface.declared_consumers):
            findings.append("inventory consumers must be text, site, or search")
        if len(set(surface.declared_consumers)) != len(surface.declared_consumers):
            findings.append("inventory consumers must not repeat")

        human_status = "not_assessed"
        provenance_status = "not_assessed"
        verified_sources: list[str] = []
        reference_status = "not_assessed"
        completeness_status = "not_applicable"
        consumer_statuses = {
            consumer: "not_applicable" if consumer not in surface.declared_consumers else "unavailable"
            for consumer in sorted(_VALID_CONSUMERS)
        }
        if surface.migration_status == "migrated":
            checks = surface.consumer_checks or {}
            if set(checks) != set(surface.declared_consumers):
                findings.append("migrated surface must verify every declared consumer and no others")
            if surface.builder is None:
                findings.append("migrated surface must declare a payload builder")
            if not surface.expected_source_paths or surface.declarations is None:
                findings.append("migrated surface must declare expected source paths and declaration access")
            else:
                try:
                    declarations = surface.declarations()
                    if not declarations:
                        raise ValueError("no declarations returned")
                    for declaration in declarations:
                        if declaration.filename not in surface.expected_source_paths:
                            raise ValueError(f"declared in {declaration.filename}, expected one of {', '.join(surface.expected_source_paths)}")
                        verified_sources.append(declaration.filename)
                    provenance_status = "verified"
                except (TypeError, ValueError, KeyError) as error:
                    provenance_status = "mismatch"
                    findings.append(f"source provenance mismatch: {error}")
            if surface.builder is not None:
                payload: dict[str, Any] | None = None
                try:
                    payload = surface.builder()
                    validate_human_mapping(payload.get("human"), owner=surface.owner)
                    human_status = "valid"
                    if surface.handle.startswith("operation."):
                        completeness_status = "complete"
                except (TypeError, ValueError, KeyError) as error:
                    human_status = "invalid"
                    findings.append(f"invalid human content: {error}")
                else:
                    try:
                        help_cli._validate_human_references(payload)
                        reference_status = "valid"
                    except (TypeError, ValueError, KeyError) as error:
                        reference_status = "broken"
                        findings.append(f"broken human references: {error}")
                if payload is not None:
                    for consumer in surface.declared_consumers:
                        check = checks.get(consumer)
                        if check is None:
                            consumer_statuses[consumer] = "failed"
                            continue
                        try:
                            if consumer == "search" and prepared_search_index is not None:
                                check(payload, prepared_search_index)
                            else:
                                check(payload)
                            consumer_statuses[consumer] = "verified"
                        except (TypeError, ValueError, KeyError) as error:
                            consumer_statuses[consumer] = "failed"
                            findings.append(f"failed {consumer} human-consumer check: {error}")
        elif surface.builder is not None:
            findings.append("unmigrated surface must not declare a canonical-human builder")
        elif surface.consumer_checks:
            findings.append("unmigrated surface must not declare canonical-human consumer checks")

        if findings:
            failed = True
        surfaces.append(
            {
                "handle": surface.handle,
                "migration_status": surface.migration_status,
                "owner": surface.owner,
                "human_content": human_status,
                "source_provenance": provenance_status,
                "verified_source_paths": sorted(set(verified_sources)),
                "reference_integrity": reference_status,
                "operation_human_completeness": completeness_status,
                "site_boundary": surface.site_boundary,
                "declared_consumers": list(surface.declared_consumers),
                "human_consumers": [
                    {"name": consumer, "status": consumer_statuses[consumer]}
                    for consumer in sorted(_VALID_CONSUMERS)
                ],
                "findings": findings,
            }
        )

    renderer_findings = _renderer_source_findings()
    if renderer_findings:
        failed = True
    migrated = sum(surface["migration_status"] == "migrated" for surface in surfaces)
    unmigrated = len(surfaces) - migrated
    return {
        "document_kind": "human_help_coverage_audit",
        "status": "fail" if failed else "pass",
        "scope": "structural coverage and reference integrity",
        "prose_quality_assessed": False,
        "note": "This audit proves structural coverage and reference integrity, not prose quality.",
        "summary": {"total": len(surfaces), "migrated": migrated, "unmigrated": unmigrated},
        "renderer_human_declarations": "fail" if renderer_findings else "verified",
        "renderer_findings": renderer_findings,
        "surfaces": surfaces,
    }


def render_human_help_coverage_report(report: dict[str, object]) -> str:
    """Render the deterministic developer-facing audit report."""

    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "Human help coverage audit",
        f"Status: {report['status']}",
        "Scope: structural coverage and reference integrity",
        "This audit proves structural coverage and reference integrity, not prose quality.",
        f"Surfaces: {summary['total']} total; {summary['migrated']} migrated; {summary['unmigrated']} unmigrated.",
        "",
    ]
    for surface in report["surfaces"]:
        assert isinstance(surface, dict)
        declared_consumers = ", ".join(surface["declared_consumers"])
        human_consumers = ", ".join(
            f"{item['name']}={item['status']}" for item in surface["human_consumers"]
        )
        lines.append(
            f"- {surface['handle']} [{surface['migration_status']}]: "
            f"owner={surface['owner']}; human={surface['human_content']}; provenance={surface['source_provenance']}; "
            f"references={surface['reference_integrity']}; declared_consumers={declared_consumers}; "
            f"completeness={surface['operation_human_completeness']}; human_consumers={human_consumers}"
        )
        if surface["site_boundary"]:
            lines.append(f"  site_boundary: {surface['site_boundary']}")
        for finding in surface["findings"]:
            lines.append(f"  finding: {finding}")
        for source_path in surface["verified_source_paths"]:
            lines.append(f"  verified_source: {source_path}")
    lines.append(f"Renderer human declarations: {report['renderer_human_declarations']}")
    for finding in report["renderer_findings"]:
        lines.append(f"  finding: {finding}")
    lines.append("")
    lines.append("Unmigrated surfaces report declared route consumers only; their human-consumer coverage is unavailable.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the read-only human-help coverage audit."""

    parser = argparse.ArgumentParser(prog="ordo-human-help-audit")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parsed = parser.parse_args(argv)
    report = build_human_help_coverage_report()
    if parsed.as_json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_human_help_coverage_report(report))
        sys.stdout.write("\n")
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
