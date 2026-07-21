"""Public CLI entrypoint for ordo-help discovery."""

from __future__ import annotations

import argparse
import json
import sys

from ordo.connectors import get_public_connector_registry
from ordo.introspection import describe_capabilities, describe_examples_catalog, describe_operations, describe_playbook_contract, describe_profile_contract, describe_state_contract, describe_system, describe_workflow_contract
from ordo.runtime.representation_adapters import describe_representation_adapter_surface
from ordo.model.runtime import Mode, RuntimeStatus
from ordo.model.json import JSONObject


PUBLIC_TOPICS: tuple[dict[str, str], ...] = (
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "capabilities", "summary": "Inspect supported and unsupported surfaces"},
    {"name": "model", "summary": "Inspect the main authoring contracts"},
    {"name": "command-line", "summary": "Inspect the public command-line launch surface"},
    {"name": "operations", "summary": "Inspect the public connector catalog"},
    {"name": "examples", "summary": "Inspect verified repository examples"},
    {"name": "operation", "summary": "Inspect one public operation by reference"},
    {"name": "describe", "summary": "Resolve a supported public topic"},
    {"name": "search", "summary": "Search topics, contract facts, and operation references"},
)

DESCRIBABLE_TOPICS: tuple[str, ...] = ("overview", "capabilities", "model", "command-line", "operations", "examples")

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help overview --json", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help capabilities --json", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help model --json", "purpose": "Learn the main DSL surfaces"},
    {"command": "ordo-help command-line --json", "purpose": "Inspect public launch commands and flags"},
    {"command": "ordo-help operations --json", "purpose": "Inspect the public operation catalog"},
    {"command": "ordo-help examples --json", "purpose": "Inspect verified repository examples"},
)


def build_root_response() -> JSONObject:
    """Return the machine-readable root discovery response."""

    system = describe_system()
    internal_sections = system["sections"]
    return {
        "tool_name": "ordo-help",
        "purpose": "Self-describing discovery CLI for Ordo",
        "output_modes": ["text", "json"],
        "topics": [dict(topic) for topic in PUBLIC_TOPICS],
        "recommended_first_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS],
        "examples": [
            "ordo-help overview --json",
            "ordo-help capabilities --json",
            "ordo-help model --json",
            "ordo-help command-line --json",
            "ordo-help operations --json",
            "ordo-help examples --json",
        ],
        "introspection": {
            "version": system["introspection_version"],
            "entrypoint": internal_sections["discovery"]["entrypoint"],
            "published_sections": sorted(name for name in internal_sections if name != "discovery"),
        },
    }


def build_overview_response() -> JSONObject:
    """Return the aggregated overview discovery response."""

    system = describe_system()
    operations = describe_operations()
    document_kinds = []
    for name, payload in system["sections"].items():
        if name == "discovery":
            continue
        if isinstance(payload, dict) and isinstance(payload.get("document_kind"), str):
            document_kinds.append(payload["document_kind"])

    return {
        "document_kind": "overview",
        "purpose": "World map for Ordo discovery and authoring bootstrap",
        "document_kinds": sorted(set(document_kinds)),
        "execution_concepts": {
            "modes": [mode.value for mode in Mode],
            "statuses": [status.value for status in RuntimeStatus],
        },
        "connector_namespaces": [connector["namespace"] for connector in operations["connectors"]],
        "published_topics": [topic["name"] for topic in PUBLIC_TOPICS],
        "recommended_next_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS[1:]],
    }


def build_model_response() -> JSONObject:
    """Return the aggregated model discovery response."""

    return {
        "document_kind": "model",
        "workflow": describe_workflow_contract(),
        "profile": describe_profile_contract(),
        "playbook": describe_playbook_contract(),
        "state": describe_state_contract(),
        "representation_adapters": describe_representation_adapter_surface(),
    }


def build_command_line_response() -> JSONObject:
    """Return the aggregated command-line discovery response."""

    workflow_contract = describe_workflow_contract()
    input_contract = workflow_contract["inputs_contract"]
    playbook_flags = [
        {"name": "--file", "value_shape": "PATH", "required": False, "effect": "override_playbook_discovery", "summary": "Use one explicit playbook file path"},
        {"name": "--profile", "value_shape": "NAME", "required": False, "effect": "select_active_profile", "summary": "Select one named profile for this run"},
        {"name": "--input", "value_shape": "KEY=VALUE", "required": False, "repeatable": True, "effect": "override_input_inline", "summary": "Add or override one top-level workflow input from an inline YAML value"},
        {"name": "--input-file", "value_shape": "KEY=PATH", "required": False, "repeatable": True, "effect": "override_input_from_file", "summary": "Add or override one top-level workflow input from a raw UTF-8 file string"},
        {"name": "--json", "required": False, "effect": "emit_json", "summary": "Emit JSON without extra decoration"},
    ]
    return {
        "document_kind": "command_line",
        "commands": [
            {
                "name": "ordo-playbook",
                "purpose": "Browse playbook workflows or launch one named workflow into one runtime mode",
                "usage": "ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--json] <command>",
                "discovery_commands": [
                    {"name": "workflows list", "summary": "list declared playbook workflows with project-local descriptions"},
                    {"name": "workflows show <workflow>", "summary": "show one workflow entry with file metadata and root-declared inputs"},
                ],
                "modes": [
                    {"name": "check <workflow>", "summary": "check whether the workflow can be run now, without making changes"},
                    {"name": "plan <workflow>", "summary": "show what the workflow would do, without making changes"},
                    {"name": "explain <workflow>", "summary": "explain why the workflow can or cannot be run right now"},
                    {"name": "run <workflow>", "summary": "run the workflow and do the real work"},
                    {"name": "next <workflow>", "summary": "suggest the next workflow step to run now"},
                ],
                "run_success_surface": "successful run emits the accumulated workflow-authored results list",
                "flags": playbook_flags,
                "input_override_precedence": [
                    f"workflow.inputs declares the allowed activation keys; declared keys are required at activation={str(input_contract['declared_keys_required_at_activation']).lower()}",
                    "profile.inputs may supply values for declared workflow inputs",
                    "--input overrides workflow and profile-provided values for one run",
                    "--input-file overrides workflow and profile-provided values for one run",
                    f"unknown activation inputs are rejected={str(input_contract['rejects_unknown_activation_inputs']).lower()}",
                    "when both --input and --input-file set the same key, --input-file wins",
                ],
                "examples": [
                    "ordo-playbook workflows list",
                    "ordo-playbook workflows show inspect-issue",
                    "ordo-playbook plan inspect-issue",
                    "ordo-playbook --profile review plan inspect-issue",
                    "ordo-playbook --input enabled=true plan inspect-issue",
                    "ordo-playbook --input-file body=./prompt.md plan inspect-issue",
                ],
            }
        ],
    }


def build_operation_response(reference: str) -> JSONObject | None:
    """Return the focused operation discovery response for one reference."""

    registry = get_public_connector_registry()
    connector_name, separator, operation_name = reference.partition(".")
    if not separator:
        return None

    connector = registry.get_connector(connector_name)
    operation = registry.get_operation(reference)
    if connector is None or operation is None:
        return None

    return {
        "document_kind": "operation",
        "reference": reference,
        "namespace": connector.namespace,
        "bootstrap": connector.bootstrap.to_contract(),
        "operation": operation.to_contract(),
        "related_commands": {
            "operations": "ordo-help operations --json",
            "capabilities": "ordo-help capabilities --json",
        },
        "operation_name": operation_name,
    }


def _build_capability_lookup() -> dict[str, JSONObject]:
    payload = describe_capabilities()
    lookup: dict[str, JSONObject] = {}
    for capability in payload["capabilities"]:
        lookup[capability["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "capability",
            **capability,
        }
    for rule in payload["negative_rules"]:
        lookup[rule["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "negative_rule",
            **rule,
        }
    return lookup


def _build_model_node_lookup() -> dict[str, JSONObject]:
    model = build_model_response()
    lookup: dict[str, JSONObject] = {}

    def add_node(name: str, *, contract: str, node_category: str, summary: str, metadata: JSONObject) -> None:
        lookup[name] = {
            "document_kind": "model_node",
            "node_kind": node_category,
            "name": name,
            "contract": contract,
            "summary": summary,
            "metadata": metadata,
        }

    for field in model["workflow"]["top_level_fields"]:
        add_node(f"workflow.{field['name']}", contract="workflow", node_category="field", summary="Published workflow field metadata", metadata=field)
    add_node(
        "workflow.inputs_contract",
        contract="workflow",
        node_category="input_contract",
        summary="Published workflow activation-input contract metadata",
        metadata=model["workflow"]["inputs_contract"],
    )
    add_node(
        "workflow.include_contract",
        contract="workflow",
        node_category="include_contract",
        summary="Published workflow include-resolution contract metadata",
        metadata=model["workflow"]["include_contract"],
    )
    for field in model["workflow"]["include_contract"].get("call_fields", []):
        add_node(
            f"workflow.include.{field['name']}",
            contract="workflow",
            node_category="include_field",
            summary="Published included-fragment call field metadata",
            metadata=field,
        )
    for field in model["workflow"]["include_contract"].get("fragment_metadata_fields", []):
        add_node(
            f"workflow.fragment.{field['name']}",
            contract="workflow",
            node_category="fragment_metadata_field",
            summary="Published included-fragment metadata field",
            metadata=field,
        )
    add_node(
        "workflow.run_contract",
        contract="workflow",
        node_category="run_contract",
        summary="Published workflow fragment-run contract metadata",
        metadata=model["workflow"]["run_contract"],
    )
    for field in model["workflow"]["run_contract"].get("call_fields", []):
        add_node(
            f"workflow.run.{field['name']}",
            contract="workflow",
            node_category="run_field",
            summary="Published workflow fragment-run call field metadata",
            metadata=field,
        )
    add_node(
        "workflow.value_expression_root.args",
        contract="workflow",
        node_category="expression_root",
        summary="Published included-fragment argument expression root metadata",
        metadata={
            "name": "args",
            "surface": "value_expression",
            "access_surface": model["workflow"]["include_contract"].get("fragment_argument_access_surface"),
            "state_scope": model["workflow"]["include_contract"].get("state_scope"),
            "step_scope": model["workflow"]["include_contract"].get("step_scope"),
        },
    )
    add_node(
        "workflow.local_expression.adapter_seam",
        contract="workflow",
        node_category="adapter_seam",
        summary="Published shared representation-adapter seam metadata",
        metadata=model["representation_adapters"]["shared_seam"],
    )
    add_node(
        "workflow.local_expression.adapter_binding",
        contract="workflow",
        node_category="adapter_binding",
        summary="Published outer representation-adapter binding metadata",
        metadata={
            "outer_binding_form": model["representation_adapters"]["shared_seam"]["outer_binding_form"],
            "host_binding_rules": model["representation_adapters"]["shared_seam"]["host_binding_rules"],
        },
    )
    for adapter in model["representation_adapters"]["families"]:
        add_node(
            f"workflow.local_expression.adapter.{adapter['name']}",
            contract="workflow",
            node_category="adapter_family",
            summary="Published representation-adapter family metadata",
            metadata=adapter,
        )
    for form in model["workflow"]["step_forms"]:
        add_node(
            f"workflow.step_forms.{form['name']}",
            contract="workflow",
            node_category="step_form",
            summary="Published workflow step-form metadata",
            metadata=form,
        )
        for field_name in form.get("required_fields", []):
            add_node(
                f"workflow.step.{field_name}",
                contract="workflow",
                node_category="step_field",
                summary="Published workflow step field metadata",
                metadata={"name": field_name, "required_in_forms": [form["name"]]},
            )
        for field_name in form.get("optional_fields", []):
            existing = lookup.get(f"workflow.step.{field_name}")
            if existing is not None:
                existing["metadata"].setdefault("optional_in_forms", []).append(form["name"])
                continue
            add_node(
                f"workflow.step.{field_name}",
                contract="workflow",
                node_category="step_field",
                summary="Published workflow step field metadata",
                metadata={"name": field_name, "optional_in_forms": [form["name"]]},
            )
    for field in model["profile"]["top_level_fields"]:
        add_node(f"profile.{field['name']}", contract="profile", node_category="field", summary="Published profile field metadata", metadata=field)
    for field in model["profile"]["override_fields"]:
        add_node(f"profile.overrides.{field['name']}", contract="profile", node_category="override_field", summary="Published profile override field metadata", metadata=field)
    for field in model["playbook"]["top_level_fields"]:
        add_node(f"playbook.{field['name']}", contract="playbook", node_category="field", summary="Published playbook field metadata", metadata=field)
    if "pre_run" in model["playbook"].get("activation_semantics", {}):
        add_node(
            "playbook.pre_run_contract",
            contract="playbook",
            node_category="pre_run_contract",
            summary="Published playbook pre-run contract metadata",
            metadata=model["playbook"]["activation_semantics"]["pre_run"],
        )
    for field in model["playbook"].get("pre_run_entry_fields", []):
        add_node(
            f"playbook.pre_run.{field['name']}",
            contract="playbook",
            node_category="pre_run_entry_field",
            summary="Published playbook pre-run entry field metadata",
            metadata=field,
        )
    for field in model["playbook"]["defaults_fields"]:
        add_node(f"playbook.defaults.{field['name']}", contract="playbook", node_category="default_field", summary="Published playbook default field metadata", metadata=field)
    for field in model["playbook"]["workflow_entry_fields"]:
        add_node(f"playbook.workflows.{field['name']}", contract="playbook", node_category="workflow_entry_field", summary="Published playbook workflow-entry field metadata", metadata=field)
    for field in model["playbook"]["profile_entry_fields"]:
        add_node(f"playbook.profiles.{field['name']}", contract="playbook", node_category="profile_entry_field", summary="Published playbook profile-entry field metadata", metadata=field)
    for field in model["playbook"]["state_entry_fields"]:
        add_node(f"playbook.states.{field['name']}", contract="playbook", node_category="state_entry_field", summary="Published playbook state-entry field metadata", metadata=field)

    for field_name, value in model["state"]["workflow_surface"].items():
        add_node(
            f"state.workflow_surface.{field_name}",
            contract="state",
            node_category="workflow_surface_field",
            summary="Published state workflow-surface metadata",
            metadata={"name": field_name, "value": value},
        )
    return lookup


def _build_command_line_node_lookup() -> dict[str, JSONObject]:
    payload = build_command_line_response()
    lookup: dict[str, JSONObject] = {}

    for command in payload["commands"]:
        command_name = command["name"]
        lookup[f"command-line.{command_name}"] = {
            "document_kind": "command_line_node",
            "node_kind": "command",
            "name": f"command-line.{command_name}",
            "summary": "Published command-line command metadata",
            "metadata": command,
        }
        for flag in command.get("flags", []):
            normalized = flag["name"].lstrip("-").replace("-", "_")
            lookup[f"command-line.{command_name}.flag.{normalized}"] = {
                "document_kind": "command_line_node",
                "node_kind": "flag",
                "name": f"command-line.{command_name}.flag.{normalized}",
                "summary": "Published command-line flag metadata",
                "metadata": flag,
            }
    return lookup


def build_search_response(query: str) -> JSONObject:
    """Return search results across public topics and operation references."""

    lowered_query = query.strip().lower()
    operation_results = []
    for connector in describe_operations()["connectors"]:
        namespace = connector["namespace"]
        for operation in connector["operations"]:
            reference = f"{namespace}.{operation['name']}"
            searchable = " ".join(
                [
                    reference,
                    operation["name"],
                    operation["kind"],
                    operation.get("summary") or "",
                ]
            ).lower()
            if lowered_query in searchable:
                operation_results.append(
                    {
                        "reference": reference,
                        "summary": operation.get("summary"),
                        "command": f"ordo-help operation {reference} --json",
                    }
                )

    topic_results = []
    for topic in PUBLIC_TOPICS:
        searchable = f"{topic['name']} {topic['summary']}".lower()
        if lowered_query in searchable:
            command = f"ordo-help {topic['name']} --json"
            if topic["name"] == "operation":
                command = "ordo-help operation <reference> --json"
            elif topic["name"] == "describe":
                command = "ordo-help describe <topic> --json"
            elif topic["name"] == "search":
                command = "ordo-help search <query> --json"
            topic_results.append(
                {
                    "name": topic["name"],
                    "summary": topic["summary"],
                    "command": command,
                }
            )

    fact_results = []
    for capability in describe_capabilities()["capabilities"]:
        searchable = " ".join([capability["name"], capability["scope"], capability["status"]]).lower()
        if lowered_query in searchable:
            fact_results.append(
                {
                    "kind": "capability",
                    "name": capability["name"],
                    "summary": f"Capability in scope '{capability['scope']}' is {capability['status']}",
                    "topic": "capabilities",
                    "command": f"ordo-help describe {capability['name']} --json",
                }
            )

    for rule in describe_capabilities()["negative_rules"]:
        searchable = " ".join([rule["name"], rule["surface"], rule["rule"], rule["reason"]]).lower()
        if lowered_query in searchable:
            fact_results.append(
                {
                    "kind": "negative_rule",
                    "name": rule["name"],
                    "summary": rule["rule"],
                    "topic": "capabilities",
                    "command": f"ordo-help describe {rule['name']} --json",
                }
            )

    for node_name, node in _build_model_node_lookup().items():
        searchable = f"{node_name} {json.dumps(node['metadata'], sort_keys=True)} {node['summary']}".lower()
        if lowered_query in searchable:
            fact_results.append(
                {
                    "kind": "model_field",
                    "name": node_name,
                    "summary": node["summary"],
                    "topic": "model",
                    "command": f"ordo-help describe {node_name} --json",
                }
            )

    for node_name, node in _build_command_line_node_lookup().items():
        searchable = f"{node_name} {json.dumps(node['metadata'], sort_keys=True)} {node['summary']}".lower()
        if lowered_query in searchable:
            fact_results.append(
                {
                    "kind": "command_line_field",
                    "name": node_name,
                    "summary": node["summary"],
                    "topic": "command-line",
                    "command": f"ordo-help describe {node_name} --json",
                }
            )

    for example in describe_examples_catalog()["examples"]:
        searchable = " ".join([example["name"], example["path"], *example["shows"], *example["related_topics"]]).lower()
        if lowered_query in searchable:
            fact_results.append(
                {
                    "kind": "example",
                    "name": example["name"],
                    "summary": f"Verified example at {example['path']}",
                    "topic": "examples",
                    "command": "ordo-help examples --json",
                }
            )

    return {
        "document_kind": "search_results",
        "query": query,
        "topics": topic_results,
        "facts": fact_results,
        "operations": operation_results,
    }


def render_root_text() -> str:
    """Return the human-readable bootstrap screen."""

    lines = [
        "ordo-help",
        "Self-describing discovery CLI for Ordo.",
        "",
        "Output modes:",
        "- text",
        "- json (--json)",
        "",
        "Topics:",
    ]
    for topic in PUBLIC_TOPICS:
        lines.append(f"- {topic['name']}: {topic['summary']}")
    lines.extend(
        [
            "",
            "Recommended first calls:",
            "1. ordo-help overview --json",
            "2. ordo-help capabilities --json",
            "3. ordo-help model --json",
            "4. ordo-help command-line --json",
            "5. ordo-help operations --json",
            "6. ordo-help examples --json",
            "",
            "Next command examples:",
            "- ordo-help overview --json",
            "- ordo-help capabilities --json",
            "- ordo-help model --json",
            "- ordo-help command-line --json",
            "- ordo-help operations --json",
            "- ordo-help examples --json",
        ]
    )
    return "\n".join(lines)


def render_overview_text(payload: JSONObject) -> str:
    """Return the text overview surface."""

    lines = [
        "overview",
        payload["purpose"],
        "",
        "Document kinds:",
    ]
    lines.extend(f"- {item}" for item in payload["document_kinds"])
    lines.extend(
        [
            "",
            "Execution concepts:",
            f"- modes: {', '.join(payload['execution_concepts']['modes'])}",
            f"- statuses: {', '.join(payload['execution_concepts']['statuses'])}",
            "",
            "Connector namespaces:",
        ]
    )
    lines.extend(f"- {namespace}" for namespace in payload["connector_namespaces"])
    return "\n".join(lines)


def render_capabilities_text(payload: JSONObject) -> str:
    """Return the text capabilities surface."""

    capabilities = payload["capabilities"]
    lines = ["capabilities", "Supported and unsupported runtime surfaces.", "", "Capability states:"]
    for capability in capabilities:
        summary = f"- {capability['name']}: {capability['status']}"
        related = capability.get("related_capabilities") or []
        if related:
            summary = f"{summary} (related: {', '.join(related)})"
        must_not_infer = capability.get("must_not_infer") or []
        if must_not_infer:
            summary = f"{summary} (must not infer: {', '.join(must_not_infer)})"
        lines.append(summary)
    return "\n".join(lines)


def render_model_text(payload: JSONObject) -> str:
    """Return the text model surface."""

    lines = [
        "model",
        "Main authoring contracts exposed by Ordo.",
        "",
        "Contracts:",
        f"- workflow: {payload['workflow']['document_kind']}",
        f"- profile: {payload['profile']['document_kind']}",
        f"- playbook: {payload['playbook']['document_kind']}",
        f"- state: {payload['state']['document_kind']}",
        "",
        "Representation adapters:",
        f"- outer binding form: {payload['representation_adapters']['shared_seam']['outer_binding_form']}",
    ]
    for family in payload["representation_adapters"]["families"]:
        lines.append(f"- {family['name']}: selectors={', '.join(family['selectors'])}; actions={', '.join(family['actions'])}")
    return "\n".join(lines)


def render_command_line_text(payload: JSONObject) -> str:
    """Return the text command-line surface."""

    lines = ["command-line", "Public launch commands and stable flags.", ""]
    for command in payload["commands"]:
        lines.extend([command["name"], command["purpose"], f"usage: {command['usage']}", f"modes: {', '.join(command['modes'])}", "", "flags:"])
        for flag in command["flags"]:
            suffix = f" {flag.get('value_shape', '')}".rstrip()
            lines.append(f"- {flag['name']}{suffix}: {flag['summary']}")
        lines.extend(["", "input override precedence:"])
        lines.extend(f"- {item}" for item in command["input_override_precedence"])
    return "\n".join(lines)


def render_operations_text(payload: JSONObject) -> str:
    """Return the text operations surface."""

    lines = ["operations", "Public connector namespaces and operations.", ""]
    for connector in payload["connectors"]:
        operation_names = ", ".join(operation["name"] for operation in connector["operations"])
        lines.append(f"- {connector['namespace']}: {operation_names}")
    return "\n".join(lines)


def render_examples_text(payload: JSONObject) -> str:
    """Return the text verified-examples surface."""

    lines = ["examples", "Verified repository examples published for discovery.", ""]
    for example in payload["examples"]:
        shows = ", ".join(example["shows"])
        lines.append(f"- {example['name']}: {example['path']} ({shows})")
    return "\n".join(lines)


def render_operation_text(payload: JSONObject) -> str:
    """Return the text single-operation surface."""

    operation = payload["operation"]
    lines = [
        payload["reference"],
        operation["summary"] or "No summary published.",
        "",
        f"kind: {operation['kind']}",
        f"namespace: {payload['namespace']}",
        f"maturity: {operation['maturity']}",
    ]
    if operation["inputs"]:
        lines.extend(["", "inputs:"])
        for name, shape in operation["inputs"].items():
            lines.append(f"- {name}: {shape}")
    if operation["outputs"]:
        lines.extend(["", "outputs:"])
        for name, shape in operation["outputs"].items():
            lines.append(f"- {name}: {shape}")
    if operation["failure_modes"]:
        lines.extend(["", "failure modes:"])
        for mode in operation["failure_modes"]:
            lines.append(f"- {mode}")
    return "\n".join(lines)


def render_capability_node_text(payload: JSONObject) -> str:
    """Return the text capability-node surface."""

    lines = [payload["name"], payload["node_kind"]]
    if payload["node_kind"] == "capability":
        lines.extend([f"status: {payload['status']}", f"scope: {payload['scope']}"])
    else:
        lines.extend([f"surface: {payload['surface']}", payload["rule"]])
    return "\n".join(lines)


def render_model_node_text(payload: JSONObject) -> str:
    """Return the text model-node surface."""

    lines = [payload["name"], payload["summary"], "", f"contract: {payload['contract']}", f"node kind: {payload['node_kind']}"]
    return "\n".join(lines)


def render_command_line_node_text(payload: JSONObject) -> str:
    """Return the text command-line-node surface."""

    return "\n".join([payload["name"], payload["summary"], "", f"node kind: {payload['node_kind']}"])


def render_search_text(payload: JSONObject) -> str:
    """Return the text search surface."""

    lines = [f"search: {payload['query']}"]
    if payload["topics"]:
        lines.extend(["", "Topic matches:"])
        for topic in payload["topics"]:
            lines.append(f"- {topic['name']}: {topic['command']}")
    if payload["facts"]:
        lines.extend(["", "Fact matches:"])
        for fact in payload["facts"]:
            lines.append(f"- {fact['name']} ({fact['kind']}): {fact['command']}")
    if payload["operations"]:
        lines.extend(["", "Operation matches:"])
        for operation in payload["operations"]:
            lines.append(f"- {operation['reference']}: {operation['command']}")
    if not payload["topics"] and not payload["facts"] and not payload["operations"]:
        lines.extend(["", "No topic, fact, or operation matches found."])
    return "\n".join(lines)


def _emit_payload(payload: JSONObject, *, as_json: bool, renderer) -> int:
    """Emit one discovery payload in JSON or text mode."""

    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(renderer(payload))
    sys.stdout.write("\n")
    return 0


def _emit_unknown_operation(reference: str, *, as_json: bool) -> int:
    """Emit a focused unknown-operation error."""

    payload = {
        "document_kind": "operation_error",
        "reference": reference,
        "status": "unknown_operation",
        "message": f"Unknown public operation reference '{reference}'",
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(payload["message"])
        sys.stderr.write("\n")
    return 1


def _emit_unknown_topic(topic: str, *, as_json: bool) -> int:
    """Emit a focused unknown-topic error."""

    payload = {
        "document_kind": "topic_error",
        "topic": topic,
        "status": "unknown_topic",
        "message": f"Unsupported public topic or node '{topic}'",
        "supported_topics": list(DESCRIBABLE_TOPICS),
        "supported_node_kinds": ["capability", "negative_rule", "model_node"],
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(payload["message"])
        sys.stderr.write("\n")
    return 1


def _resolve_public_topic(topic: str) -> tuple[JSONObject, object] | None:
    """Resolve one describable public topic to its payload and renderer."""

    if topic == "overview":
        return build_overview_response(), render_overview_text
    if topic == "capabilities":
        return describe_capabilities(), render_capabilities_text
    if topic == "model":
        return build_model_response(), render_model_text
    if topic == "command-line":
        return build_command_line_response(), render_command_line_text
    if topic == "operations":
        return describe_operations(), render_operations_text
    if topic == "examples":
        return describe_examples_catalog(), render_examples_text
    capability_node = _build_capability_lookup().get(topic)
    if capability_node is not None:
        return capability_node, render_capability_node_text
    model_node = _build_model_node_lookup().get(topic)
    if model_node is not None:
        return model_node, render_model_node_text
    command_line_node = _build_command_line_node_lookup().get(topic)
    if command_line_node is not None:
        return command_line_node, render_command_line_node_text
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the ordo-help CLI."""

    parser = argparse.ArgumentParser(prog="ordo-help", add_help=False)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    subparsers = parser.add_subparsers(dest="command")

    overview_parser = subparsers.add_parser("overview", add_help=False)
    overview_parser.add_argument("--json", action="store_true", dest="as_json")

    capabilities_parser = subparsers.add_parser("capabilities", add_help=False)
    capabilities_parser.add_argument("--json", action="store_true", dest="as_json")

    model_parser = subparsers.add_parser("model", add_help=False)
    model_parser.add_argument("--json", action="store_true", dest="as_json")

    command_line_parser = subparsers.add_parser("command-line", add_help=False)
    command_line_parser.add_argument("--json", action="store_true", dest="as_json")

    operations_parser = subparsers.add_parser("operations", add_help=False)
    operations_parser.add_argument("--json", action="store_true", dest="as_json")

    examples_parser = subparsers.add_parser("examples", add_help=False)
    examples_parser.add_argument("--json", action="store_true", dest="as_json")

    operation_parser = subparsers.add_parser("operation", add_help=False)
    operation_parser.add_argument("reference")
    operation_parser.add_argument("--json", action="store_true", dest="as_json")

    describe_parser = subparsers.add_parser("describe", add_help=False)
    describe_parser.add_argument("topic")
    describe_parser.add_argument("--json", action="store_true", dest="as_json")

    search_parser = subparsers.add_parser("search", add_help=False)
    search_parser.add_argument("query")
    search_parser.add_argument("--json", action="store_true", dest="as_json")

    parsed = parser.parse_args(argv)
    as_json = bool(getattr(parsed, "as_json", False))

    if parsed.command is None:
        if as_json:
            json.dump(build_root_response(), sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0

        sys.stdout.write(render_root_text())
        sys.stdout.write("\n")
        return 0

    if parsed.command == "overview":
        return _emit_payload(build_overview_response(), as_json=as_json, renderer=render_overview_text)
    if parsed.command == "capabilities":
        return _emit_payload(describe_capabilities(), as_json=as_json, renderer=render_capabilities_text)
    if parsed.command == "model":
        return _emit_payload(build_model_response(), as_json=as_json, renderer=render_model_text)
    if parsed.command == "command-line":
        return _emit_payload(build_command_line_response(), as_json=as_json, renderer=render_command_line_text)
    if parsed.command == "operations":
        return _emit_payload(describe_operations(), as_json=as_json, renderer=render_operations_text)
    if parsed.command == "examples":
        return _emit_payload(describe_examples_catalog(), as_json=as_json, renderer=render_examples_text)
    if parsed.command == "operation":
        payload = build_operation_response(parsed.reference)
        if payload is None:
            return _emit_unknown_operation(parsed.reference, as_json=as_json)
        return _emit_payload(payload, as_json=as_json, renderer=render_operation_text)
    if parsed.command == "describe":
        resolved = _resolve_public_topic(parsed.topic)
        if resolved is None:
            return _emit_unknown_topic(parsed.topic, as_json=as_json)
        payload, renderer = resolved
        return _emit_payload(payload, as_json=as_json, renderer=renderer)
    if parsed.command == "search":
        return _emit_payload(build_search_response(parsed.query), as_json=as_json, renderer=render_search_text)

    parser.error(f"Unsupported command: {parsed.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
