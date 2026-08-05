"""Concrete YAML representation-adapter family."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ordo.model.json import JSONValue
import yaml

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
class _FilterStep:
    mode: str
    field: str
    operator: str
    expected: _ActionArgument


@dataclass(frozen=True, slots=True)
class _ActionArgument:
    kind: str
    value: object


def _register() -> None:
    register_representation_adapter(
        "yaml",
        _evaluate_yaml_invocation,
        metadata=RepresentationAdapterMetadata(
            name="yaml",
            summary="Select values from one YAML document through exact structural paths and immediate-child filters.",
            selectors=(
                ".field",
                '["literal-key"]',
                "[n]",
                ".one(field=value)",
                ".one(field!=value)",
                ".many(field=value)",
                ".many(field!=value)",
            ),
            actions=(),
            shortcuts=(),
        ),
    )


def _evaluate_yaml_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    if not isinstance(invocation.root_value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="YAML adapter requires a string root value",
            details={"family": invocation.family, "actual_type": type(invocation.root_value).__name__},
        )
    root_value = _load_root_yaml(invocation.root_value)
    steps = _parse_yaml_body(invocation.body)
    return adapter_read_result(_evaluate_yaml_steps(steps, root_value, invocation.parameters))


def _load_root_yaml(root_text: str) -> JSONValue:
    try:
        loaded = yaml.safe_load(root_text)
    except yaml.YAMLError as exc:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="YAML adapter requires one valid YAML document representable as canonical JSON-shaped data",
            details={"family": "yaml", "source_code": "load.yaml.syntax"},
        ) from exc
    return _normalize_yaml_value(loaded)


def _normalize_yaml_value(value: object) -> JSONValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [_normalize_yaml_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_root_value",
                    message="YAML adapter requires string mapping keys",
                    details={"family": "yaml", "actual_key_type": type(key).__name__},
                )
            normalized[key] = _normalize_yaml_value(item)
        return normalized
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_root_value",
        message="YAML adapter requires values representable as canonical JSON-shaped data",
        details={"family": "yaml", "actual_type": type(value).__name__},
    )


def _parse_yaml_body(body: str) -> tuple[object, ...]:
    position = 0
    steps: list[object] = []
    while position < len(body):
        char = body[position]
        if char.isspace():
            position += 1
            continue
        if body.startswith("->", position):
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_action",
                message="YAML adapter is read-only in the MVP",
                details={"body": body, "position": position},
            )
        if body.startswith("..", position):
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_path",
                message="YAML adapter does not support recursive descent in the MVP",
                details={"body": body, "position": position},
            )
        if char == ".":
            filter_step, next_position = _try_parse_filter_step(body, position)
            if filter_step is not None:
                steps.append(filter_step)
                position = next_position
                continue
            step, position = _parse_dot_step(body, position)
            steps.append(step)
            continue
        if char == "[":
            step, position = _parse_bracket_step(body, position)
            steps.append(step)
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML adapter body contains unsupported syntax",
            details={"body": body, "position": position},
        )
    return tuple(steps)


def _parse_dot_step(body: str, start: int) -> tuple[_MemberStep, int]:
    match = re.match(r"\.([A-Za-z_][A-Za-z0-9_]*)", body[start:])
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML adapter expected a member name after '.'",
            details={"body": body, "position": start},
        )
    return _MemberStep(key=match.group(1)), start + len(match.group(0))


def _try_parse_filter_step(body: str, start: int) -> tuple[_FilterStep, int] | tuple[None, int]:
    for mode in ("one", "many"):
        prefix = f".{mode}("
        if not body.startswith(prefix, start):
            continue
        close = _find_closing_paren(body, start + len(prefix) - 1)
        argument_text = body[start + len(prefix) : close].strip()
        field, operator, expected = _parse_filter_argument(argument_text, body=body, position=start)
        return _FilterStep(mode=mode, field=field, operator=operator, expected=expected), close + 1
    return None, start


def _find_closing_paren(body: str, open_paren: int) -> int:
    position = open_paren + 1
    depth = 1
    quote: str | None = None
    escape = False
    while position < len(body):
        char = body[position]
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            position += 1
            continue
        if char in {'"', "'"}:
            quote = char
            position += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return position
        position += 1
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message="YAML filter expected closing ')'",
        details={"body": body, "position": open_paren},
    )


def _parse_filter_argument(argument_text: str, *, body: str, position: int) -> tuple[str, str, _ActionArgument]:
    if not argument_text:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML filter requires one field=value or field!=value argument",
            details={"body": body, "position": position},
        )
    match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(!=|=)\s*(.+?)\s*", argument_text)
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML filter requires one field=value or field!=value argument",
            details={"body": body, "position": position},
        )
    field, operator, value_text = match.groups()
    return field, operator, _parse_filter_argument_value(value_text.strip(), body=body, position=position)


def _parse_filter_argument_value(argument_text: str, *, body: str, position: int) -> _ActionArgument:
    try:
        return _ActionArgument(kind="literal", value=json.loads(argument_text))
    except json.JSONDecodeError:
        pass
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument_text):
        return _ActionArgument(kind="parameter", value=argument_text)
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message="YAML filter arguments must be one JSON literal or parameter name",
        details={"body": body, "position": position},
    )


def _parse_bracket_step(body: str, start: int) -> tuple[object, int]:
    end = body.find("]", start + 1)
    if end == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML adapter expected ']' in bracket selector",
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
            message="YAML bracket selectors must use an integer index or JSON string literal",
            details={"body": body, "position": start},
        ) from exc
    if not isinstance(key, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML string-key selectors must resolve to a string",
            details={"body": body, "position": start},
        )
    return _MemberStep(key=key), end + 1


def _evaluate_yaml_steps(steps: tuple[object, ...], root_value: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue:
    current = root_value
    for step in steps:
        if isinstance(step, _MemberStep):
            if not isinstance(current, dict):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="YAML member selection requires an object focus",
                    details={"key": step.key, "actual_type": type(current).__name__},
                )
            if step.key not in current:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"YAML member '{step.key}' was not found",
                    details={"key": step.key},
                )
            current = current[step.key]
            continue
        if isinstance(step, _IndexStep):
            if not isinstance(current, list):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="YAML array indexing requires a list focus",
                    details={"index": step.index, "actual_type": type(current).__name__},
                )
            if step.index >= len(current):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"YAML array index {step.index} was not found",
                    details={"index": step.index},
                )
            current = current[step.index]
            continue
        if isinstance(step, _FilterStep):
            current = _evaluate_filter_step(step, current, parameters)
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="YAML adapter encountered an unknown path step",
            details={"step_type": type(step).__name__},
        )
    return current


def _evaluate_filter_step(step: _FilterStep, current: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue:
    candidates = _iter_filter_candidates(current)
    expected = _resolve_filter_argument(step.expected, parameters)
    matches = [
        candidate
        for candidate in candidates
        if _candidate_matches_filter(candidate, field=step.field, operator=step.operator, expected=expected)
    ]
    if step.mode == "many":
        return matches
    if not matches:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_not_found",
            message=f"YAML one() found no child with {step.field}{step.operator}{expected!r}",
            details={"field": step.field, "operator": step.operator, "expected": expected},
        )
    if len(matches) > 1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous_match",
            message=f"YAML one() found multiple children with {step.field}{step.operator}{expected!r}",
            details={"field": step.field, "operator": step.operator, "expected": expected, "match_count": len(matches)},
        )
    return matches[0]


def _iter_filter_candidates(current: JSONValue) -> list[JSONValue]:
    if isinstance(current, list):
        return list(current)
    if isinstance(current, dict):
        return list(current.values())
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message="YAML one()/many() require an object or array focus",
        details={"actual_type": type(current).__name__},
    )


def _resolve_filter_argument(argument: _ActionArgument, parameters: dict[str, JSONValue]) -> JSONValue:
    if argument.kind == "literal":
        return _normalize_yaml_value(argument.value)
    assert argument.kind == "parameter"
    name = str(argument.value)
    if name not in parameters:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message=f"YAML filter parameter '{name}' was not provided",
            details={"parameter": name},
        )
    return _normalize_yaml_value(parameters[name])


def _candidate_matches_filter(candidate: JSONValue, *, field: str, operator: str, expected: JSONValue) -> bool:
    if not isinstance(candidate, dict) or field not in candidate:
        return False
    actual = candidate[field]
    if operator == "=":
        return actual == expected
    assert operator == "!="
    return actual != expected


_register()
