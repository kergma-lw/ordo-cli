"""Concrete JSON representation-adapter family."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ordo.model.json import JSONValue

from .representation_adapters import (
    RepresentationAdapterError,
    RepresentationAdapterInvocation,
    RepresentationAdapterMetadata,
    RepresentationAdapterResult,
    adapter_read_result,
    register_representation_adapter,
)


@dataclass(frozen=True, slots=True)
class _MemberStep:
    key: str


@dataclass(frozen=True, slots=True)
class _IndexStep:
    index: int


@dataclass(frozen=True, slots=True)
class _JsonPlan:
    steps: tuple[object, ...]


def _register() -> None:
    register_representation_adapter(
        "json",
        _evaluate_json_invocation,
        metadata=RepresentationAdapterMetadata(
            name="json",
            summary="Select values from strict JSON text through exact structural paths.",
            selectors=(".field", '["literal-key"]', "[n]"),
            actions=(),
            shortcuts=(),
        ),
    )


def _evaluate_json_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    if not isinstance(invocation.root_value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="JSON adapter requires a string root value",
            details={"family": invocation.family, "actual_type": type(invocation.root_value).__name__},
        )
    try:
        root_value = json.loads(invocation.root_value)
    except json.JSONDecodeError as exc:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="JSON adapter requires valid JSON text",
            details={"family": invocation.family},
        ) from exc
    plan = _parse_json_body(invocation.body)
    value = _evaluate_json_plan(plan, root_value)
    return adapter_read_result(value)


def _parse_json_body(body: str) -> _JsonPlan:
    position = 0
    steps: list[object] = []
    while position < len(body):
        char = body[position]
        if char.isspace():
            position += 1
            continue
        if char == ".":
            step, position = _parse_dot_step(body, position)
            steps.append(step)
            continue
        if char == "[":
            step, position = _parse_bracket_step(body, position)
            steps.append(step)
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON adapter body contains unsupported syntax",
            details={"body": body, "position": position},
        )
    return _JsonPlan(steps=tuple(steps))


def _parse_dot_step(body: str, start: int) -> tuple[_MemberStep, int]:
    match = re.match(r"\.([A-Za-z_][A-Za-z0-9_]*)", body[start:])
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON adapter expected a member name after '.'",
            details={"body": body, "position": start},
        )
    return _MemberStep(key=match.group(1)), start + len(match.group(0))


def _parse_bracket_step(body: str, start: int) -> tuple[object, int]:
    end = body.find("]", start + 1)
    if end == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON adapter expected ']' in bracket selector",
            details={"body": body, "position": start},
        )
    inner = body[start + 1 : end].strip()
    if inner.isdigit():
        return _IndexStep(index=int(inner)), end + 1
    try:
        key = json.loads(inner)
    except json.JSONDecodeError as exc:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON bracket selectors must use an integer index or JSON string literal",
            details={"body": body, "position": start},
        ) from exc
    if not isinstance(key, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON string-key selectors must resolve to a string",
            details={"body": body, "position": start},
        )
    return _MemberStep(key=key), end + 1


def _evaluate_json_plan(plan: _JsonPlan, value: JSONValue) -> JSONValue:
    current = value
    for step in plan.steps:
        if isinstance(step, _MemberStep):
            if not isinstance(current, dict):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="JSON member selection requires an object focus",
                    details={"key": step.key, "actual_type": type(current).__name__},
                )
            if step.key not in current:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"JSON member '{step.key}' was not found",
                    details={"key": step.key},
                )
            current = current[step.key]
            continue
        if isinstance(step, _IndexStep):
            if not isinstance(current, list):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="JSON index selection requires an array focus",
                    details={"index": step.index, "actual_type": type(current).__name__},
                )
            if step.index >= len(current):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"JSON array index {step.index} was not found",
                    details={"index": step.index, "length": len(current)},
                )
            current = current[step.index]
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON selector step is not supported",
            details={"step_type": type(step).__name__},
        )
    return current


_register()
