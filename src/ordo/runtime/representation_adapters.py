"""Shared representation-adapter seam for local-expression evaluation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from ordo.model.json import JSONObject, JSONValue


@dataclass(frozen=True, slots=True)
class RepresentationAdapterInvocation:
    """Resolved invocation passed from the shared seam to one adapter family."""

    family: str
    body: str
    root_value: JSONValue
    parameters: JSONObject
    source_expression: str


@dataclass(frozen=True, slots=True)
class RepresentationAdapterResult:
    """Normalized adapter-family runtime result."""

    kind: Literal["read", "write"]
    value: JSONValue


@dataclass(frozen=True, slots=True)
class RepresentationAdapterMetadata:
    """Published introspection metadata for one adapter family."""

    name: str
    summary: str
    selectors: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    shortcuts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepresentationAdapterError(Exception):
    """Structured adapter-family failure surfaced through the shared seam."""

    code: str
    message: str
    details: JSONObject


RepresentationAdapterHandler = Callable[[RepresentationAdapterInvocation], RepresentationAdapterResult]

_REPRESENTATION_ADAPTERS: dict[str, RepresentationAdapterHandler] = {}
_REPRESENTATION_ADAPTER_METADATA: dict[str, RepresentationAdapterMetadata] = {}


def register_representation_adapter(
    family: str,
    handler: RepresentationAdapterHandler,
    *,
    metadata: RepresentationAdapterMetadata | None = None,
) -> None:
    """Register one concrete representation-adapter family handler."""

    _REPRESENTATION_ADAPTERS[family] = handler
    if metadata is not None:
        _REPRESENTATION_ADAPTER_METADATA[family] = metadata


def unregister_representation_adapter(family: str) -> None:
    """Remove one concrete representation-adapter family handler."""

    _REPRESENTATION_ADAPTERS.pop(family, None)
    _REPRESENTATION_ADAPTER_METADATA.pop(family, None)


def has_representation_adapter(family: str) -> bool:
    """Return whether one adapter family is currently registered."""

    return family in _REPRESENTATION_ADAPTERS


def describe_representation_adapter_surface() -> JSONObject:
    """Return published seam and family metadata for help/introspection."""

    return {
        "shared_seam": {
            "family_owned_body": True,
            "outer_binding_form": " with{...}",
            "read_write_boundary": {
                "read": "returns selected_or_derived_value",
                "write": "returns updated_root_value",
            },
            "host_binding_rules": [
                "host references do not appear bare inside adapter-owned body syntax",
                "outer bindings are resolved before adapter-family evaluation",
            ],
        },
        "families": [
            {
                "name": item.name,
                "summary": item.summary,
                "selectors": list(item.selectors),
                "actions": list(item.actions),
                "shortcuts": list(item.shortcuts),
            }
            for item in sorted(_REPRESENTATION_ADAPTER_METADATA.values(), key=lambda current: current.name)
        ],
    }


def adapter_read_result(value: JSONValue) -> RepresentationAdapterResult:
    """Return one normalized read invocation result."""

    return RepresentationAdapterResult(kind="read", value=value)


def adapter_write_result(updated_root_value: JSONValue) -> RepresentationAdapterResult:
    """Return one normalized write invocation result."""

    return RepresentationAdapterResult(kind="write", value=updated_root_value)


def evaluate_representation_adapter_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    """Dispatch one resolved invocation through the shared adapter seam."""

    handler = _REPRESENTATION_ADAPTERS.get(invocation.family)
    if handler is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_family_unknown",
            message=f"Unknown representation-adapter family '{invocation.family}'",
            details={"family": invocation.family, "expression": invocation.source_expression},
        )
    return handler(invocation)


from . import markdown_adapter as _markdown_adapter  # noqa: E402,F401
from . import text_adapter as _text_adapter  # noqa: E402,F401
