"""Concrete text representation-adapter family."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ordo.model.json import JSONObject, JSONValue
from .value_preview import summarize_json_value

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
class _TextSpan:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _TextScope:
    root_text: str
    span: _TextSpan

    @property
    def text(self) -> str:
        return self.root_text[self.span.start : self.span.end]


@dataclass(frozen=True, slots=True)
class _TextCollection:
    root_text: str
    kind: str
    items: tuple[_TextScope, ...]


@dataclass(frozen=True, slots=True)
class _IndexStep:
    index: int


@dataclass(frozen=True, slots=True)
class _SelectorStep:
    name: str
    argument: str | None = None


@dataclass(frozen=True, slots=True)
class _ActionArgument:
    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class _TextAction:
    name: str
    arguments: tuple[_ActionArgument, ...]


@dataclass(frozen=True, slots=True)
class _TextPlan:
    steps: tuple[object, ...]
    action: _TextAction | None = None


def _register() -> None:
    register_representation_adapter(
        "text",
        _evaluate_text_invocation,
        metadata=RepresentationAdapterMetadata(
            name="text",
            summary="Select and transform plain-text roots through literal narrowing, line projection, and terminal text mutation.",
            selectors=("lines", 'find("literal")', 'finds("literal")', 'before("literal")', 'after("literal")', "[n]"),
            actions=("append", "replace", "remove"),
        ),
    )


def _evaluate_text_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    if not isinstance(invocation.root_value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="Text adapter requires a string root value",
            details={"family": invocation.family, "actual_type": type(invocation.root_value).__name__},
        )
    plan = _parse_text_body(invocation.body)
    root_scope = _TextScope(invocation.root_value, _TextSpan(0, len(invocation.root_value)))
    selection = _evaluate_text_plan(plan, root_scope)
    if plan.action is None:
        return adapter_read_result(_selection_to_json(selection))
    updated_root = _apply_text_action(selection, plan.action, invocation.parameters)
    return adapter_write_result(updated_root)


def _parse_text_body(body: str) -> _TextPlan:
    position = 0
    steps: list[object] = []
    action: _TextAction | None = None
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
            step, position = _parse_index_step(body, position)
            steps.append(step)
            continue
        if body.startswith("->", position):
            action, position = _parse_action(body, position)
            break
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text adapter body contains unsupported syntax",
            details={"body": body, "position": position},
        )
    if position < len(body) and body[position:].strip():
        trailing_start = position + len(body[position:]) - len(body[position:].lstrip())
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text adapter body has unexpected trailing syntax",
            details={"body": body, "position": trailing_start},
        )
    return _TextPlan(steps=tuple(steps), action=action)


def _parse_dot_step(body: str, start: int) -> tuple[object, int]:
    if body.startswith(".lines", start):
        return _SelectorStep(name="lines"), start + len(".lines")
    for name in ("finds", "find", "before", "after"):
        prefix = f".{name}("
        if body.startswith(prefix, start):
            close = body.find(")", start + len(prefix))
            if close == -1:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message=f"Text {name} selector expected closing ')'",
                    details={"body": body, "position": start},
                )
            argument_text = body[start + len(prefix) : close].strip()
            try:
                argument = json.loads(argument_text)
            except json.JSONDecodeError as exc:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message=f"Text {name} selector requires a JSON string literal",
                    details={"body": body, "position": start},
                ) from exc
            if not isinstance(argument, str) or argument == "":
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message=f"Text {name} selector requires a non-empty string literal",
                    details={"body": body, "position": start},
                )
            return _SelectorStep(name=name, argument=argument), close + 1
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message="Text adapter expected a selector name after '.'",
        details={"body": body, "position": start},
    )


def _parse_index_step(body: str, start: int) -> tuple[object, int]:
    end = body.find("]", start + 1)
    if end == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text adapter expected ']' in index selector",
            details={"body": body, "position": start},
        )
    inner = body[start + 1 : end].strip()
    if not inner.isdigit():
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text index selectors must use a non-negative integer",
            details={"body": body, "position": start},
        )
    return _IndexStep(index=int(inner)), end + 1


def _parse_action(body: str, start: int) -> tuple[_TextAction, int]:
    match = re.match(r"->([A-Za-z_][A-Za-z0-9_]*)\(", body[start:])
    if match is None:
        if body.startswith("->remove()", start):
            return _TextAction(name="remove", arguments=()), start + len("->remove()")
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Unknown text action",
            details={"body": body, "position": start},
        )
    name = match.group(1)
    open_paren = start + len(match.group(0)) - 1
    close = body.find(")", open_paren + 1)
    if close == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"Text {name} action expected closing ')'",
            details={"body": body, "position": start},
        )
    argument_text = body[open_paren + 1 : close].strip()
    if name == "remove":
        if argument_text:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_action",
                message="Text remove action does not accept arguments",
                details={"body": body, "position": start},
            )
        return _TextAction(name="remove", arguments=()), close + 1
    if not argument_text:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"Text {name} action requires arguments",
            details={"body": body, "position": start},
        )
    raw_arguments = _split_action_arguments(argument_text)
    expected = {"append": (1, 1), "replace": (1, 1)}.get(name)
    if expected is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Unknown text action",
            details={"body": body, "position": start},
        )
    minimum, maximum = expected
    if len(raw_arguments) < minimum or len(raw_arguments) > maximum:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"Text {name} action received an unexpected number of arguments",
            details={"body": body, "position": start, "argument_count": len(raw_arguments)},
        )
    return _TextAction(name=name, arguments=tuple(_parse_action_argument(item, body=body, position=start) for item in raw_arguments)), close + 1


def _split_action_arguments(argument_text: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    quote: str | None = None
    escape = False
    for index, char in enumerate(argument_text):
        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == ",":
            arguments.append(argument_text[start:index].strip())
            start = index + 1
    arguments.append(argument_text[start:].strip())
    return arguments


def _parse_action_argument(argument_text: str, *, body: str, position: int) -> _ActionArgument:
    try:
        literal = json.loads(argument_text)
    except json.JSONDecodeError:
        literal = None
    if isinstance(literal, str):
        return _ActionArgument(kind="literal", value=literal)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument_text):
        return _ActionArgument(kind="parameter", value=argument_text)
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_action",
        message="Text action arguments must be string literals or parameter names",
        details={"body": body, "position": position},
    )


def _evaluate_text_plan(plan: _TextPlan, root_scope: _TextScope) -> _TextScope | _TextCollection:
    current: _TextScope | _TextCollection = root_scope
    for step in plan.steps:
        if isinstance(step, _SelectorStep):
            current = _apply_selector(current, step)
            continue
        if isinstance(step, _IndexStep):
            current = _apply_index(current, step)
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text selector step is not supported",
            details={"step_type": type(step).__name__},
        )
    return current


def _apply_selector(current: _TextScope | _TextCollection, step: _SelectorStep) -> _TextScope | _TextCollection:
    if isinstance(current, _TextCollection):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message=f"Text selector '.{step.name}' is not available after a collection focus",
            details={"selector": step.name, "collection_kind": current.kind, "observed": _summarize_text_focus(current)},
        )
    if step.name == "lines":
        return _project_lines(current)
    assert step.argument is not None
    if step.name == "find":
        matches = _find_matches(current, step.argument)
        if not matches:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_not_found",
                message=f"Text find selector found no matches for '{step.argument}'",
                details={"literal": step.argument, "observed": _summarize_text_focus(current)},
            )
        if len(matches) > 1:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_ambiguous",
                message=f"Text find selector is ambiguous for '{step.argument}'",
                details={"literal": step.argument, "matches": len(matches), "observed": _summarize_text_focus(current)},
            )
        return matches[0]
    if step.name == "finds":
        return _TextCollection(root_text=current.root_text, kind="matches", items=tuple(_find_matches(current, step.argument)))
    if step.name == "before":
        return _narrow_around_anchor(current, step.argument, mode="before")
    if step.name == "after":
        return _narrow_around_anchor(current, step.argument, mode="after")
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message=f"Unknown text selector '.{step.name}'",
        details={"selector": step.name},
    )


def _apply_index(current: _TextScope | _TextCollection, step: _IndexStep) -> _TextScope:
    if not isinstance(current, _TextCollection):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Text index selectors require a collection focus",
            details={"index": step.index, "observed": _summarize_text_focus(current)},
        )
    if step.index >= len(current.items):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_not_found",
            message=f"Text selection index {step.index} is not available",
            details={
                "index": step.index,
                "matches": len(current.items),
                "collection_kind": current.kind,
                "observed": _summarize_text_focus(current),
            },
        )
    return current.items[step.index]


def _project_lines(scope: _TextScope) -> _TextCollection:
    text = scope.text
    if text == "":
        return _TextCollection(root_text=scope.root_text, kind="lines", items=())
    items: list[_TextScope] = []
    absolute = scope.span.start
    start = absolute
    for part in text.split("\n"):
        end = start + len(part)
        items.append(_TextScope(scope.root_text, _TextSpan(start, end)))
        start = end + 1
    return _TextCollection(root_text=scope.root_text, kind="lines", items=tuple(items))


def _find_matches(scope: _TextScope, literal: str) -> list[_TextScope]:
    items: list[_TextScope] = []
    text = scope.text
    relative = 0
    while True:
        index = text.find(literal, relative)
        if index == -1:
            break
        start = scope.span.start + index
        end = start + len(literal)
        items.append(_TextScope(scope.root_text, _TextSpan(start, end)))
        relative = index + len(literal)
    return items


def _narrow_around_anchor(scope: _TextScope, literal: str, *, mode: str) -> _TextScope:
    matches = _find_matches(scope, literal)
    if not matches:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_not_found",
            message=f"Text {mode} selector found no matches for '{literal}'",
            details={"literal": literal, "observed": _summarize_text_focus(scope)},
        )
    if len(matches) > 1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous",
            message=f"Text {mode} selector is ambiguous for '{literal}'",
            details={"literal": literal, "matches": len(matches), "observed": _summarize_text_focus(scope)},
        )
    match = matches[0]
    if mode == "before":
        return _TextScope(scope.root_text, _TextSpan(scope.span.start, match.span.start))
    return _TextScope(scope.root_text, _TextSpan(match.span.end, scope.span.end))


def _selection_to_json(selection: _TextScope | _TextCollection) -> JSONValue:
    if isinstance(selection, _TextCollection):
        return [item.text for item in selection.items]
    return selection.text


def _summarize_text_focus(value: _TextScope | _TextCollection | JSONValue) -> JSONObject:
    if isinstance(value, _TextCollection):
        preview_items = [item.text for item in value.items[:2]]
        return {
            "type": "text_collection",
            "collection_kind": value.kind,
            "length": len(value.items),
            "items_preview": preview_items,
        }
    if isinstance(value, _TextScope):
        return {
            "type": "text_scope",
            "length": len(value.text),
            "preview": value.text[:80] + ("…" if len(value.text) > 80 else ""),
        }
    return summarize_json_value(value)


def _apply_text_action(selection: _TextScope | _TextCollection, action: _TextAction, parameters: JSONObject) -> str:
    replacements: list[tuple[_TextSpan, str]]
    if isinstance(selection, _TextCollection):
        replacements = [
            (item.span, _resolve_replacement_text(action, item.text, parameters))
            for item in selection.items
        ]
    else:
        replacements = [(selection.span, _resolve_replacement_text(action, selection.text, parameters))]
    if not replacements:
        return _root_text_for_selection(selection)
    root_text = _root_text_for_selection(selection)
    parts: list[str] = []
    cursor = 0
    for span, replacement in replacements:
        parts.append(root_text[cursor : span.start])
        parts.append(replacement)
        cursor = span.end
    parts.append(root_text[cursor:])
    return "".join(parts)


def _resolve_replacement_text(action: _TextAction, current_text: str, parameters: JSONObject) -> str:
    if action.name == "remove":
        return ""
    text = _resolve_action_argument(action.arguments[0], parameters)
    if action.name == "replace":
        return text
    if action.name == "append":
        return current_text + text
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_action",
        message="Unknown text action",
        details={"action": action.name},
    )


def _resolve_action_argument(argument: _ActionArgument, parameters: JSONObject) -> str:
    if argument.kind == "literal":
        return argument.value
    value = parameters.get(argument.value)
    if not isinstance(value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"Text action parameter '{argument.value}' must resolve to a string",
            details={"parameter": argument.value, "actual_type": type(value).__name__ if value is not None else "null"},
        )
    return value


def _root_text_for_selection(selection: _TextScope | _TextCollection) -> str:
    if isinstance(selection, _TextCollection):
        return selection.root_text
    return selection.root_text


_register()
