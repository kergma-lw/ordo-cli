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
class _FilterStep:
    mode: str
    field: str
    operator: str
    expected: _ActionArgument


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

    @property
    def recursive_index(self) -> int | None:
        for index, step in enumerate(self.steps):
            if step == "..":
                return index
        return None


def _register() -> None:
    register_representation_adapter(
        "json",
        _evaluate_json_invocation,
        metadata=RepresentationAdapterMetadata(
            name="json",
            summary="Select values from strict JSON text through exact structural paths.",
            selectors=(".field", '["literal-key"]', "[n]", "..field", ".one(field=value)", ".many(field=value)", ".one(field!=value)", ".many(field!=value)"),
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
        value = _evaluate_json_plan(plan, root_value, invocation.parameters)
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
            if body.startswith("..", position):
                if steps and isinstance(steps[-1], _FilterStep) and steps[-1].mode == "many":
                    raise RepresentationAdapterError(
                        code="runtime.value.adapter_invalid_path",
                        message="JSON recursive descent cannot immediately follow many() results",
                        details={"body": body, "position": position},
                    )
                if ".." in steps:
                    raise RepresentationAdapterError(
                        code="runtime.value.adapter_invalid_path",
                        message="JSON adapter allows at most one recursive descent segment",
                        details={"body": body, "position": position},
                    )
                steps.append("..")
                position += 2
                continue
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
        if steps and steps[-1] == ".." and (char.isalpha() or char == "_"):
            step, position = _parse_bare_member_step(body, position)
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
    recursive_index = next((index for index, step in enumerate(steps) if step == ".."), None)
    if recursive_index is not None and recursive_index == len(steps) - 1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON recursive descent must be followed by structural path steps",
            details={"body": body, "position": len(body.rstrip()) - 2},
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


def _parse_bare_member_step(body: str, start: int) -> tuple[_MemberStep, int]:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", body[start:])
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON recursive descent expected a member name",
            details={"body": body, "position": start},
        )
    return _MemberStep(key=match.group(1)), start + len(match.group(1))


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
        message="JSON filter expected closing ')'",
        details={"body": body, "position": open_paren},
    )


def _parse_filter_argument(argument_text: str, *, body: str, position: int) -> tuple[str, str, _ActionArgument]:
    if not argument_text:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON filter requires one field=value or field!=value argument",
            details={"body": body, "position": position},
        )
    match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(!=|=)\s*(.+?)\s*", argument_text)
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON filter requires one field=value or field!=value argument",
            details={"body": body, "position": position},
        )
    field, operator, value_text = match.groups()
    return field, operator, _parse_action_argument(value_text.strip(), body=body, position=position)


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
    try:
        close = _find_closing_paren(body, open_paren)
    except RepresentationAdapterError as exc:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"JSON {name} action expected closing ')'",
            details={"body": body, "position": start},
        ) from exc
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


def _evaluate_json_plan(plan: _JsonPlan, value: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue:
    recursive_index = plan.recursive_index
    if recursive_index is not None:
        prefix = tuple(plan.steps[:recursive_index])
        suffix = tuple(plan.steps[recursive_index + 1 :])
        base = _evaluate_exact_steps(prefix, value, parameters)
        return _collect_recursive_read_matches(base, suffix, parameters)
    return _evaluate_exact_steps(plan.steps, value, parameters)


def _evaluate_exact_steps(steps: tuple[object, ...], value: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue:
    current = value
    for step in steps:
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
        if isinstance(step, _FilterStep):
            current = _evaluate_filter_step(step, current, parameters)
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="JSON selector step is not supported",
            details={"step_type": type(step).__name__},
        )
    return current


def _collect_recursive_read_matches(base: JSONValue, suffix: tuple[object, ...], parameters: dict[str, JSONValue]) -> list[JSONValue]:
    matches: list[JSONValue] = []
    matched = _try_evaluate_exact_steps(suffix, base, parameters)
    if matched is not _NO_MATCH:
        matches.append(matched)
    for descendant in _iter_descendants(base):
        matches.extend(_collect_recursive_read_matches(descendant, suffix, parameters))
    return matches


def _evaluate_filter_step(step: _FilterStep, current: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue:
    candidates = _iter_filter_candidates(current)
    expected = _resolve_action_argument(step.expected, parameters)
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
            message=f"JSON one() found no child with {step.field}{step.operator}{expected!r}",
            details={"field": step.field, "operator": step.operator, "expected": expected},
        )
    if len(matches) > 1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous_match",
            message=f"JSON one() found multiple children with {step.field}{step.operator}{expected!r}",
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
        message="JSON one()/many() require an object or array focus",
        details={"actual_type": type(current).__name__},
    )


def _candidate_matches_filter(candidate: JSONValue, *, field: str, operator: str, expected: JSONValue) -> bool:
    if not isinstance(candidate, dict) or field not in candidate:
        return False
    actual = candidate[field]
    if operator == "=":
        return actual == expected
    assert operator == "!="
    return actual != expected


def _apply_json_action(plan: _JsonPlan, root_value: JSONValue, parameters: dict[str, JSONValue]) -> str:
    assert plan.action is not None
    recursive_index = plan.recursive_index
    if any(isinstance(step, _FilterStep) for step in plan.steps):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="JSON one()/many() filters do not support write actions in the MVP",
            details={"action": plan.action.name},
        )
    if plan.action.name == "set":
        if recursive_index is not None:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_action",
                message="JSON recursive descent does not support set in the MVP",
                details={},
            )
        replacement = _resolve_action_argument(plan.action.arguments[0], parameters)
        updated = _apply_set(plan.steps, root_value, replacement)
        return _serialize_json(updated)
    if plan.action.name == "remove":
        if recursive_index is not None:
            updated = _apply_recursive_remove(plan, root_value)
            return _serialize_json(updated)
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


@dataclass(frozen=True, slots=True)
class _TargetRef:
    parent: object
    step: object
    depth: int


_NO_MATCH = object()


def _try_evaluate_exact_steps(steps: tuple[object, ...], value: JSONValue, parameters: dict[str, JSONValue]) -> JSONValue | object:
    current: JSONValue = value
    for step in steps:
        if isinstance(step, _MemberStep):
            if not isinstance(current, dict) or step.key not in current:
                return _NO_MATCH
            current = current[step.key]
            continue
        if isinstance(step, _IndexStep):
            if not isinstance(current, list) or step.index >= len(current):
                return _NO_MATCH
            current = current[step.index]
            continue
        if isinstance(step, _FilterStep):
            if not isinstance(current, (dict, list)):
                return _NO_MATCH
            expected = _resolve_action_argument(step.expected, parameters)
            matches = [
                candidate
                for candidate in _iter_filter_candidates(current)
                if _candidate_matches_filter(candidate, field=step.field, operator=step.operator, expected=expected)
            ]
            if step.mode == "many":
                current = matches
                continue
            if len(matches) != 1:
                return _NO_MATCH
            current = matches[0]
            continue
        return _NO_MATCH
    return current


def _iter_descendants(value: JSONValue) -> list[JSONValue]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return list(value)
    return []


def _apply_recursive_remove(plan: _JsonPlan, root_value: JSONValue) -> JSONValue:
    recursive_index = plan.recursive_index
    assert recursive_index is not None
    prefix = tuple(plan.steps[:recursive_index])
    suffix = tuple(plan.steps[recursive_index + 1 :])
    base = _evaluate_exact_steps(prefix, root_value, {})
    targets = _collect_recursive_remove_targets(base, suffix, depth=0)
    if not targets:
        return root_value
    for target in sorted(targets, key=_target_sort_key):
        _remove_target_ref(target)
    return root_value


def _collect_recursive_remove_targets(base: JSONValue, suffix: tuple[object, ...], *, depth: int) -> list[_TargetRef]:
    targets: list[_TargetRef] = []
    target = _try_locate_target(base, suffix)
    if target is not None:
        targets.append(_TargetRef(parent=target[0], step=target[1], depth=depth))
    for descendant in _iter_descendants(base):
        targets.extend(_collect_recursive_remove_targets(descendant, suffix, depth=depth + 1))
    return targets


def _try_locate_target(value: JSONValue, steps: tuple[object, ...]) -> tuple[object, object] | None:
    if not steps:
        return None
    current: JSONValue = value
    for step in steps[:-1]:
        if isinstance(step, _MemberStep):
            if not isinstance(current, dict) or step.key not in current:
                return None
            current = current[step.key]
            continue
        assert isinstance(step, _IndexStep)
        if not isinstance(current, list) or step.index >= len(current):
            return None
        current = current[step.index]
    final_step = steps[-1]
    if isinstance(final_step, _MemberStep):
        if not isinstance(current, dict) or final_step.key not in current:
            return None
        return current, final_step
    assert isinstance(final_step, _IndexStep)
    if not isinstance(current, list) or final_step.index >= len(current):
        return None
    return current, final_step


def _target_sort_key(target: _TargetRef) -> tuple[int, int, int]:
    step = target.step
    if isinstance(step, _IndexStep):
        return (-target.depth, 0, -step.index)
    return (-target.depth, 1, 0)


def _remove_target_ref(target: _TargetRef) -> None:
    if isinstance(target.step, _MemberStep):
        assert isinstance(target.parent, dict)
        if target.step.key in target.parent:
            del target.parent[target.step.key]
        return
    assert isinstance(target.step, _IndexStep)
    assert isinstance(target.parent, list)
    if target.step.index < len(target.parent):
        target.parent.pop(target.step.index)


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
