"""Public connector contract models."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

from .human import HumanDeclaration, declare_human, human_content, human_mapping
from .json import JSONObject, JSONValue

OperationKind = Literal["probe", "action"]
_PLACEHOLDER_PATTERN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")

CONNECTOR_FEATURE_HUMAN = declare_human({
    "title": "Connectors",
    "goal": "Choose a published operation when it expresses the intended system or current-run work.",
    "summary": "Published operations for observing or changing systems, or for narrowly scoped current-run work.",
    "sections": [],
})

CONNECTOR_HUMAN: JSONObject = {
    "feature_clusters": {
        "connectors": {
            **human_mapping(CONNECTOR_FEATURE_HUMAN),
            "summary": "Published operations for observing or changing systems, or for narrowly scoped current-run work.",
            "use_when": ["A published operation expresses the product intent directly."],
            "avoid_when": ["A missing semantic capability is being hidden in local automation."],
        },
    },
}

CONNECTOR_AUTHORING_HUMAN = declare_human({
    "title": "Connector authoring",
    "goal": "Publish a connector operation only when it is the stable, narrow public surface for the work.",
    "summary": "Use connector authoring to add a clearly bounded operation with a reader-facing guide.",
    "sections": [
        {"heading": "Before publishing", "items": [
            "Prefer an existing operation or a clean composition before adding a new one.",
            "Keep the operation's purpose, inputs, effects, and failure boundaries explicit.",
        ]},
        {"heading": "Start here", "items": [
            "Browse the existing operations first, then use a routine only for a remaining mechanical project-local gap.",
            "No checked example is published because connector implementation is not a workflow shape that readers should copy.",
        ]},
        {"heading": "Extension compatibility", "items": [
            "This guide does not provide a public connector-extension dependency contract. The earlier contract has no public successor or workflow-author migration path.",
            "Use published operations and the narrow local fallback guidance for workflow work. Changes to built-in connector implementation are outside this reader guide and need their own maintained project scope.",
        ]},
        {"heading": "Related references", "references": [
            {"handle": "operations", "summary": "Browse existing public operations first."},
            {"handle": "workflow-rules", "summary": "Apply the authoring rules when choosing a fallback."},
        ]},
    ],
})


OPERATIONS_HUMAN = declare_human({
    "title": "Published operations",
    "goal": "Choose the narrowest published operation that expresses the workflow's external work.",
    "summary": "Browse operations by connector namespace, then inspect a focused operation before using it.",
    "sections": [
        {
            "heading": "Choose an operation",
            "items": [
                "A namespace groups operations for one area of work. Start with the namespace that owns the system or local state your workflow needs.",
                "Use a probe to observe facts that later workflow decisions need. Use an action when the workflow must intentionally change something.",
                "When a catalog name looks promising, inspect it with `ordo-help operation <namespace.operation>` for its focused reference before adding it to a workflow. Use `ordo-help operation <namespace.operation> --json` when you need the exact machine-readable input and result contract.",
            ],
        },
        {
            "heading": "Stay on the published path",
            "items": [
                "Prefer a published operation when it states the intended work directly. Combine published operations when each part is already available.",
                "If no published operation or clear composition fits, name the remaining gap. Use a published routine only for a narrow mechanical or intentionally project-local task; if the gap is semantic, clarify it with the user instead of encoding it locally.",
            ],
            "references": [
                {"handle": "workflow-rules.routine.*", "summary": "Apply the routine boundary before adding a project-local helper."},
            ],
        },
    ],
})


@dataclass(frozen=True, slots=True)
class PreflightObservation:
    """Canonical structured recommended probe observation template."""

    probe: str
    with_: JSONObject = field(default_factory=dict)
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.probe, str) or not self.probe or "." not in self.probe:
            raise ValueError("preflight observation probe must be a non-empty dotted public reference")
        for name, value in self.with_.items():
            if not isinstance(name, str) or not name:
                raise ValueError("preflight observation argument names must be non-empty strings")
            if not _is_json_value(value):
                raise ValueError("preflight observation argument values must be valid JSON-shaped scalar, list, or object values")
        for field_name in self.fields:
            if not isinstance(field_name, str) or not field_name:
                raise ValueError("preflight observation fields must be non-empty strings")

    def placeholder_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for value in self.with_.values():
            match = _PLACEHOLDER_PATTERN.fullmatch(value)
            if match is not None:
                names.append(match.group(1))
        return tuple(names)

    def to_contract(self) -> JSONObject:
        payload: JSONObject = {
            "probe": self.probe,
            "with": dict(self.with_),
        }
        if self.fields:
            payload["fields"] = list(self.fields)
        return payload


def _is_json_value(value: JSONValue) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


@dataclass(frozen=True, slots=True)
class ConnectorBootstrap:
    """Shared family-level prerequisites and context surface."""

    prerequisites: tuple[str, ...] = ()
    context_fields: tuple[str, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped bootstrap contract."""

        return {
            "prerequisites": list(self.prerequisites),
            "context_fields": list(self.context_fields),
        }


@dataclass(frozen=True, slots=True)
class OperationContract:
    """Public operation contract surface, independent of implementation internals."""

    name: str
    kind: OperationKind
    summary: str | None = None
    inputs: JSONObject = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    outputs: JSONObject = field(default_factory=dict)
    failure_modes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[JSONObject, ...] = ()
    maturity: str = "stable"
    deprecated: bool = False
    replaced_by: tuple[str, ...] = ()
    invalidates_observations: tuple[str, ...] = ()
    preflight_observations: tuple[PreflightObservation, ...] = ()
    human: HumanDeclaration | JSONObject | None = None

    def human_declaration(self) -> HumanDeclaration:
        if not isinstance(self.human, HumanDeclaration):
            raise ValueError(f"Operation '{self.name}' must declare canonical human content beside its operation declaration")
        human = self.human.content
        sections = human.get("sections", [])
        if len(sections) < 2 or any(not section.get("items") and not section.get("body") for section in sections):
            raise ValueError(f"Operation '{self.name}' human content must include substantive decision sections")
        return self.human

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped operation contract."""

        return {
            "name": self.name,
            "kind": self.kind,
            "summary": self.summary,
            "inputs": dict(self.inputs),
            "prerequisites": list(self.prerequisites),
            "effects": list(self.effects),
            "outputs": dict(self.outputs),
            "failure_modes": list(self.failure_modes),
            "tags": list(self.tags),
            "examples": [dict(example) for example in self.examples],
            "maturity": self.maturity,
            "deprecated": self.deprecated,
            "replaced_by": list(self.replaced_by),
            "invalidates_observations": list(self.invalidates_observations),
            "preflight_observations": [item.to_contract() for item in self.preflight_observations],
            "human": human_content(self.human_declaration(), owner=self.name),
        }


@dataclass(frozen=True, slots=True)
class Connector:
    """Public connector family and its stable operation registry surface."""

    namespace: str
    bootstrap: ConnectorBootstrap = field(default_factory=ConnectorBootstrap)
    operations: tuple[OperationContract, ...] = ()

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped connector contract."""

        return {
            "namespace": self.namespace,
            "bootstrap": self.bootstrap.to_contract(),
            "operations": [operation.to_contract() for operation in self.operations],
        }


@dataclass(frozen=True, slots=True)
class ConnectorRegistry:
    """Discoverable public registry of stable connector families and operations."""

    connectors: tuple[Connector, ...]

    def list_connectors(self) -> tuple[Connector, ...]:
        return self.connectors

    def get_connector(self, namespace: str) -> Connector | None:
        for connector in self.connectors:
            if connector.namespace == namespace:
                return connector
        return None

    def get_operation(self, reference: str) -> OperationContract | None:
        namespace, separator, operation_name = reference.partition(".")
        if not separator:
            return None

        connector = self.get_connector(namespace)
        if connector is None:
            return None

        for operation in connector.operations:
            if operation.name == operation_name:
                return operation
        return None

    def to_contract(self) -> JSONObject:
        return {"connectors": [connector.to_contract() for connector in self.connectors]}


def operations_catalog_human(connectors: list[JSONObject]) -> HumanDeclaration:
    """Build the reader-facing catalog grouping beside the connector contract."""

    content = deepcopy(OPERATIONS_HUMAN.content)
    groups = []
    for connector in connectors:
        namespace = str(connector["namespace"])
        operations = connector.get("operations", [])
        names = []
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            label = f"{namespace}.{operation['name']} ({operation['kind']})"
            if namespace == "shell" and operation["name"] == "command":
                label += " [legacy-only; do not use for new workflows]"
            names.append(label)
        groups.append({"heading": namespace, "items": names})
    content["sections"].append({"heading": "Catalog by namespace", "subsections": groups})
    return HumanDeclaration(content=content, filename=OPERATIONS_HUMAN.filename)
