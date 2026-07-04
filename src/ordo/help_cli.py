"""Public CLI entrypoint for ordo-help discovery."""

from __future__ import annotations

import argparse
import json
import sys

from ordo.connectors import get_public_connector_registry
from ordo.introspection import describe_capabilities, describe_examples_catalog, describe_operations, describe_playbook_contract, describe_profile_contract, describe_state_contract, describe_system, describe_workflow_contract
from ordo.model.runtime import Mode, RuntimeStatus
from ordo.model.json import JSONObject


PUBLIC_TOPICS: tuple[dict[str, str], ...] = (
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "capabilities", "summary": "Inspect supported and unsupported surfaces"},
    {"name": "model", "summary": "Inspect the main authoring contracts"},
    {"name": "operations", "summary": "Inspect the public connector catalog"},
    {"name": "examples", "summary": "Inspect verified repository examples"},
    {"name": "operation", "summary": "Inspect one public operation by reference"},
    {"name": "describe", "summary": "Resolve a supported public topic"},
    {"name": "search", "summary": "Search topics, contract facts, and operation references"},
)

DESCRIBABLE_TOPICS: tuple[str, ...] = ("overview", "capabilities", "model", "operations", "examples")

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help overview --json", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help capabilities --json", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help model --json", "purpose": "Learn the main DSL surfaces"},
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
                    "command": "ordo-help capabilities --json",
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
                    "command": "ordo-help capabilities --json",
                }
            )

    model = build_model_response()
    contract_field_groups = (
        ("workflow", model["workflow"], ("top_level_fields", "step_forms", "step_form_rules", "guard_forms")),
        ("profile", model["profile"], ("top_level_fields", "override_fields")),
        ("playbook", model["playbook"], ("top_level_fields", "workflow_entry_fields", "profile_entry_fields", "state_entry_fields", "defaults_fields")),
        ("state", model["state"], ("workflow_surface",)),
    )
    for contract_name, payload, keys in contract_field_groups:
        for key in keys:
            section = payload.get(key)
            if isinstance(section, list):
                for item in section:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name") or item.get("field")
                    if not isinstance(name, str):
                        continue
                    searchable = f"{contract_name} {json.dumps(item, sort_keys=True)}".lower()
                    if lowered_query in searchable:
                        fact_results.append(
                            {
                                "kind": "model_field",
                                "name": f"{contract_name}.{name}",
                                "summary": f"Published field metadata under the {contract_name} contract",
                                "topic": "model",
                                "command": "ordo-help model --json",
                            }
                        )
            elif isinstance(section, dict):
                for field_name, field_value in section.items():
                    searchable = f"{field_name} {json.dumps(field_value, sort_keys=True)}".lower()
                    if lowered_query in searchable:
                        fact_results.append(
                            {
                                "kind": "model_field",
                                "name": f"{contract_name}.{field_name}",
                                "summary": f"Published field metadata under the {contract_name} contract",
                                "topic": "model",
                                "command": "ordo-help model --json",
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
            "4. ordo-help operations --json",
            "5. ordo-help examples --json",
            "",
            "Next command examples:",
            "- ordo-help overview --json",
            "- ordo-help capabilities --json",
            "- ordo-help model --json",
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
        lines.append(f"- {capability['name']}: {capability['status']}")
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
    ]
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
    return "\n".join(lines)


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
        "message": f"Unsupported public topic '{topic}'",
        "supported_topics": list(DESCRIBABLE_TOPICS),
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
    if topic == "operations":
        return describe_operations(), render_operations_text
    if topic == "examples":
        return describe_examples_catalog(), render_examples_text
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
