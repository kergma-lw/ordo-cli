"""Concrete key-value representation-adapter family."""

from __future__ import annotations

from ordo.model.json import JSONValue

from .representation_adapters import (
    RepresentationAdapterError,
    RepresentationAdapterInvocation,
    RepresentationAdapterMetadata,
    RepresentationAdapterResult,
    adapter_read_result,
    register_representation_adapter,
)


def _register() -> None:
    register_representation_adapter(
        "key_value",
        _evaluate_key_value_invocation,
        metadata=RepresentationAdapterMetadata(
            name="key_value",
            summary="Interpret a plain-text root as a flat key/value object using a required literal separator parameter.",
            selectors=(),
            actions=(),
            shortcuts=(),
        ),
    )


def _evaluate_key_value_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    if not isinstance(invocation.root_value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="Key-value adapter requires a string root value",
            details={"family": invocation.family, "actual_type": type(invocation.root_value).__name__},
        )
    if invocation.body.strip():
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Key-value adapter does not support adapter-owned path syntax in the MVP",
            details={"family": invocation.family, "body": invocation.body},
        )
    separator = invocation.parameters.get("separator")
    if not isinstance(separator, str) or separator == "":
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_parameter",
            message="Key-value adapter requires a non-empty string separator parameter",
            details={"family": invocation.family, "parameter": "separator"},
        )
    return adapter_read_result(_parse_key_value_root(invocation.root_value, separator=separator))


def _parse_key_value_root(root_text: str, *, separator: str) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {}
    for line_number, raw_line in enumerate(root_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        separator_index = line.find(separator)
        if separator_index == -1:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_parameter",
                message="Key-value adapter record is missing the configured separator",
                details={"line_number": line_number, "separator": separator},
            )
        key = line[:separator_index].strip()
        if key == "":
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_parameter",
                message="Key-value adapter does not allow empty keys",
                details={"line_number": line_number, "separator": separator},
            )
        value = _normalize_value(line[separator_index + len(separator) :].strip())
        if key in result:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_ambiguous",
                message=f"Key-value adapter found duplicate key '{key}'",
                details={"line_number": line_number, "key": key},
            )
        result[key] = value
    return result


def _normalize_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


_register()
