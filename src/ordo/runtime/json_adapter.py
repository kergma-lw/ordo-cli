"""Concrete JSON representation-adapter family."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re

from ordo.model.json import JSONValue

from .representation_adapters import (
    RepresentationAdapterError,
    RepresentationAdapterInvocation,
    RepresentationAdapterMetadata,
    RepresentationAdapterResult,
    adapter_read_result,
    adapter_write_result,
    register_representation_adapter,
)


@dataclass(frozen=True, slots=True)
class _MemberStep:
    key: str


@dataclass(frozen=True, slots=True)
class _IndexStep:
    index: int


@dataclass(frozen=True, slots=True)
class _ActionArgument:
    kind: str
    value: object


@dataclass(frozen=True, slots=True)
class _JsonAction:
    name: str
    arguments: tuple[_ActionArgument, ...]


@dataclass(frozen=True, slots=True)
class _JsonPlan:
    steps: tuple[object, ...]
    action: _JsonAction | None = None


def _register() -> None:
    register_representation_adapter(
        "json",
        _evaluate_json_invocation,
        metadata=RepresentationAdapterMetadata(
            name="json",
            summary="Select values from strict JSON text through exact structural paths.",
            selectors=(".field", '["literal-key"]', "[n]"),
            actions=("set", "remove"),
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
    if plan.action is None:
        value = _evaluate_json_plan(plan, root_value)
        return adapter_read_result(value)
    updated_root = _apply_json_action(plan, root_value, invocation.parameters)
    return adapter_write_result(updated_root)


def _parse_json_body(body: str) -> _JsonPlan:
    position = 0
    steps: list[object] = []
    action: _JsonAction | None = None
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
        if body.startswith("->", position):
            action, position = _parse_action(body, position)
            break
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON adapter body contains unsupported syntax",
            details={"body": body, "position": position},
        )
    if position < len(body) and body[position:].strip():
        trailing_start = position + len(body[position:]) - len(body[position:].lstrip())
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON adapter body has unexpected trailing syntax",
            details={"body": body, "position": trailing_start},
        )
    return _JsonPlan(steps=tuple(steps), action=action)


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


def _parse_action(body: str, start: int) -> tuple[_JsonAction, int]:
    match = re.match(r"->([A-Za-z_][A-Za-z0-9_]*)\(", body[start:])
    if match is None:
        if body.startswith("->remove()", start):
            return _JsonAction(name="remove", arguments=()), start + len("->remove()")
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Unknown JSON action",
            details={"body": body, "position": start},
        )
    name = match.group(1)
    open_paren = start + len(match.group(0)) - 1
    close = body.find(")", open_paren + 1)
    if close == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"JSON {name} action expected closing ')'",
            details={"body": body, "position": start},
        )
    argument_text = body[open_paren + 1 : close].strip()
    if name == "remove":
        if argument_text:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_action",
                message="JSON remove action does not accept arguments",
                details={"body": body, "position": start},
            )
        return _JsonAction(name="remove", arguments=()), close + 1
    if name != "set":
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Unknown JSON action",
            details={"body": body, "position": start},
        )
    if not argument_text:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="JSON set action requires one argument",
            details={"body": body, "position": start},
        )
    return _JsonAction(name="set", arguments=(_parse_action_argument(argument_text, body=body, position=start),)), close + 1


def _parse_action_argument(argument_text: str, *, body: str, position: int) -> _ActionArgument:
    try:
        return _ActionArgument(kind="literal", value=json.loads(argument_text))
    except json.JSONDecodeError:
        pass
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument_text):
        return _ActionArgument(kind="parameter", value=argument_text)
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_action",
        message="JSON action arguments must be one JSON literal or parameter name",
        details={"body": body, "position": position},
    )


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


def _apply_json_action(plan: _JsonPlan, root_value: JSONValue, parameters: dict[str, JSONValue]) -> str:
    assert plan.action is not None
    if plan.action.name == "set":
        replacement = _resolve_action_argument(plan.action.arguments[0], parameters)
        updated = _apply_set(plan.steps, root_value, replacement)
        return _serialize_json(updated)
    if plan.action.name == "remove":
        updated = _apply_remove(plan.steps, root_value)
        return _serialize_json(updated)
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_action",
        message="Unknown JSON action",
        details={"action": plan.action.name},
    )


def _apply_set(steps: tuple[object, ...], root_value: JSONValue, replacement: JSONValue) -> JSONValue:
    if not steps:
        return replacement
    parent = _resolve_parent_for_write(root_value, steps, auto_create=True)
    final_step = steps[-1]
    if isinstance(final_step, _MemberStep):
        if not isinstance(parent, dict):
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_path",
                message="JSON member selection requires an object focus",
                details={"key": final_step.key, "actual_type": type(parent).__name__},
            )
        parent[final_step.key] = replacement
        return root_value
    assert isinstance(final_step, _IndexStep)
    if not isinstance(parent, list):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON index selection requires an array focus",
            details={"index": final_step.index, "actual_type": type(parent).__name__},
        )
    if final_step.index >= len(parent):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_not_found",
            message=f"JSON array index {final_step.index} was not found",
            details={"index": final_step.index, "length": len(parent)},
        )
    parent[final_step.index] = replacement
    return root_value


def _apply_remove(steps: tuple[object, ...], root_value: JSONValue) -> JSONValue:
    if not steps:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="JSON remove requires an explicit member or array element target",
            details={},
        )
    parent = _resolve_parent_for_write(root_value, steps, auto_create=False)
    final_step = steps[-1]
    if isinstance(final_step, _MemberStep):
        if not isinstance(parent, dict):
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_path",
                message="JSON member selection requires an object focus",
                details={"key": final_step.key, "actual_type": type(parent).__name__},
            )
        if final_step.key not in parent:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_not_found",
                message=f"JSON member '{final_step.key}' was not found",
                details={"key": final_step.key},
            )
        del parent[final_step.key]
        return root_value
    assert isinstance(final_step, _IndexStep)
    if not isinstance(parent, list):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON index selection requires an array focus",
            details={"index": final_step.index, "actual_type": type(parent).__name__},
        )
    if final_step.index >= len(parent):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_not_found",
            message=f"JSON array index {final_step.index} was not found",
            details={"index": final_step.index, "length": len(parent)},
        )
    parent.pop(final_step.index)
    return root_value


def _resolve_parent_for_write(root_value: JSONValue, steps: tuple[object, ...], *, auto_create: bool) -> JSONValue:
    current = root_value
    for step in steps[:-1]:
        if isinstance(step, _MemberStep):
            if not isinstance(current, dict):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="JSON member selection requires an object focus",
                    details={"key": step.key, "actual_type": type(current).__name__},
                )
            if step.key not in current:
                if not auto_create:
                    raise RepresentationAdapterError(
                        code="runtime.value.adapter_not_found",
                        message=f"JSON member '{step.key}' was not found",
                        details={"key": step.key},
                    )
                current[step.key] = {}
            current = current[step.key]
            continue
        assert isinstance(step, _IndexStep)
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
    return current


def _resolve_action_argument(argument: _ActionArgument, parameters: dict[str, JSONValue]) -> JSONValue:
    value = argument.value if argument.kind == "literal" else parameters.get(str(argument.value))
    return _require_json_compatible(value, parameter_name=str(argument.value) if argument.kind == "parameter" else None)


def _require_json_compatible(value: object, *, parameter_name: str | None) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _invalid_action_value(parameter_name, type(value).__name__)
        return value
    if isinstance(value, list):
        return [_require_json_compatible(item, parameter_name=parameter_name) for item in value]
    if isinstance(value, dict):
        converted: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _invalid_action_value(parameter_name, type(value).__name__)
            converted[key] = _require_json_compatible(item, parameter_name=parameter_name)
        return converted
    raise _invalid_action_value(parameter_name, type(value).__name__)


def _invalid_action_value(parameter_name: str | None, actual_type: str) -> RepresentationAdapterError:
    if parameter_name is None:
        message = "JSON action literal must be JSON-compatible"
        details = {"actual_type": actual_type}
    else:
        message = f"JSON action parameter '{parameter_name}' must resolve to a JSON-compatible value"
        details = {"parameter": parameter_name, "actual_type": actual_type}
    return RepresentationAdapterError(
        code="runtime.value.adapter_invalid_action",
        message=message,
        details=details,
    )


def _serialize_json(value: JSONValue) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


_register()
